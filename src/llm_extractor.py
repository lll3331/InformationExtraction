import asyncio
import time
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel


class MagnetocaloricData(BaseModel):
    """磁热材料数据结构：6个必填字段"""
    alloy_composition: str = Field(description="合金化学成分，如 Ni50Mn35Sn15")
    sample_preparation: str = Field(description="样品制备/获取方法，如 感应熔炼+退火+淬火")
    max_magnetic_entropy: str = Field(description="最大磁熵变数值及单位，如 18.5 J/kg·K")
    temperature: str = Field(description="最大磁熵变对应的温度及单位，如 310 K")
    magnetic_field: str = Field(description="测量时外加磁场及单位，如 5 T")
    source_pdf: str = Field(description="来源PDF文件名，用于溯源")


class MagnetocaloricDataList(BaseModel):
    """包装为列表以兼容 with_structured_output"""
    data: List[MagnetocaloricData] = Field(default_factory=list, description="磁热材料数据列表")


def setup_logger(log_path: Path) -> logging.Logger:
    """配置日志：文件滚动 + 控制台输出"""
    logger = logging.getLogger("LLMExtractor")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024,
        backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


class BatchExtractor:
    """
    异步批量从 MD 文件中提取结构化数据。
    使用 llm.with_structured_output(MagnetocaloricDataList) 强制输出 JSON。
    """

    def __init__(
        self,
        input_folder: Path,
        output_folder: Path,
        llm: BaseChatModel,
        system_prompt: str,
        max_concurrent: int = 10
    ) -> None:
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.llm = llm
        self.system_prompt = system_prompt
        self.max_concurrent = max_concurrent

        # 绑定结构化输出
        self.structured_llm = self.llm.with_structured_output(MagnetocaloricDataList)

        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.log_path = self.output_folder / "processing_log.txt"
        self.logger = setup_logger(self.log_path)

        self.processed = 0
        self.failed = 0
        self.total = 0

    def log(self, msg: str, level: str = "info") -> None:
        if level == "error":
            self.logger.error(msg)
        elif level == "warning":
            self.logger.warning(msg)
        else:
            self.logger.info(msg)

    async def _process_single(self, md_file: Path, index: int) -> Tuple[bool, float]:
        """处理单个 MD 文件"""
        start = time.time()
        start_str = datetime.now().strftime("%H:%M:%S")

        try:
            # 读取并清理内容
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 过滤参考文献等章节
            content = self._filter_content(content)

            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"**Paper content**\n{content}")
            ]

            # 调用 LLM
            response = await self.structured_llm.ainvoke(messages)

            # 写入 JSON
            out_file = self.output_folder / f"{md_file.stem}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(response.model_dump() if hasattr(response, "model_dump") else response, f, ensure_ascii=False, indent=2)

            elapsed = time.time() - start
            self.processed += 1
            self.log(f"[{index}/{self.total}] OK: {md_file.name} ({elapsed:.1f}s)")

            return True, elapsed

        except Exception as e:
            elapsed = time.time() - start
            self.failed += 1
            self.log(f"[{index}/{self.total}] FAIL: {md_file.name} ({e})", "error")
            return False, elapsed

    def _filter_content(self, content: str) -> str:
        """过滤掉参考文献、致谢等章节"""
        excluded = ["ACKNOWLEDGMENT", "REFERENCES", "参考文献", "Supplementary"]
        lines = []
        skip = False
        for line in content.split("\n"):
            up = line.upper().replace(" ", "")
            if any(ex in up for ex in excluded):
                skip = True
                continue
            skip = False
            if not skip:
                lines.append(line)
        return "\n".join(lines)

    async def run(self) -> None:
        """异步执行所有文件"""
        md_files = list(self.input_folder.rglob("*.md"))
        self.total = len(md_files)

        if self.total == 0:
            self.log(f"No .md files found in {self.input_folder}", "error")
            return

        start_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log("=== Batch MD→JSON Started ===")
        self.log(f"Start: {start_str} | Input: {self.input_folder} | Output: {self.output_folder}")
        self.log(f"Concurrent: {self.max_concurrent} | Total: {self.total}")
        self.log("")

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def bounded_task(md_file: Path, i: int):
            async with semaphore:
                return await self._process_single(md_file, i)

        tasks = [bounded_task(f, i) for i, f in enumerate(md_files, 1)]
        await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - self.start_time if hasattr(self, "start_time") else 0
        self.log("")
        self.log("=== Batch Completed ===")
        self.log(f"Processed: {self.processed} | Failed: {self.failed} | Success: {self.processed/self.total*100:.1f}%")

    def run_batch(self) -> None:
        """同步入口，启动异步任务"""
        self.start_time = time.time()
        asyncio.run(self.run())
        self.total_time = time.time() - self.start_time
        self.log(f"Total time: {self.total_time:.1f}s ({self.total_time/60:.1f}min)")