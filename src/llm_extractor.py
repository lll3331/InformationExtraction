"""LLM异步批量提取器核心模块"""
import asyncio
import time
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pydantic import BaseModel
from typing import Optional, List, Tuple, Type, Union

import json

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel


def setup_logger(log_path: Path) -> logging.Logger:
    """
    配置日志：文件滚动 + 控制台输出

    参数:
        log_path: 日志文件路径

    返回:
        logging.Logger: 配置好的日志记录器
    """
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

    参数:
        input_folder: MD文件所在目录
        output_folder: JSON输出目录
        llm: LangChain聊天模型实例
        system_prompt: 系统提示词
        output_model: Pydantic模型类，用于with_structured_output
        max_concurrent: 最大并发数，默认10
        exclude_sections: 要过滤掉的章节标题关键词列表
    """

    def __init__(
        self,
        input_folder: Path,
        output_folder: Path,
        llm: BaseChatModel,
        system_prompt: str,
        output_model: Type[BaseModel],
        max_concurrent: int = 10,
        exclude_sections: Optional[List[str]] = None
    ) -> None:
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.llm = llm
        self.system_prompt = system_prompt
        self.max_concurrent = max_concurrent
        self.exclude_sections = exclude_sections or [
            "ACKNOWLEDGMENT", "REFERENCES", "参考文献", "Supplementary"
        ]

        self.structured_llm = self.llm.with_structured_output(output_model)

        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.log_path = self.output_folder / "processing_log.txt"
        self.logger = setup_logger(self.log_path)

        self.processed: int = 0
        self.failed: int = 0
        self.total: int = 0
        self.start_time: Optional[float] = None

    def log(self, msg: str, level: str = "info") -> None:
        """统一日志方法"""
        if level == "error":
            self.logger.error(msg)
        elif level == "warning":
            self.logger.warning(msg)
        else:
            self.logger.info(msg)

    async def _process_single(self, md_file: Path, index: int) -> Tuple[bool, float]:
        """
        处理单个MD文件

        参数:
            md_file: MD文件路径
            index: 文件在处理队列中的索引

        返回:
            Tuple[bool, float]: (是否成功, 处理耗时秒数)
        """
        start = time.time()

        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            content = self._filter_content(content)

            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"**Paper content**\n{content}")
            ]

            response = await self.structured_llm.ainvoke(messages)

            out_file = self.output_folder / f"{md_file.stem}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                if hasattr(response, "model_dump"):
                    result_data = response.model_dump()
                else:
                    result_data = response
                # 添加 source_md 字段，用于溯源
                result_data["source_md"] = md_file.name
                json.dump(result_data, f, ensure_ascii=False, indent=2)

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
        """
        过滤掉参考文献、致谢等章节，仅当行首出现标题行时重置跳过状态

        参数:
            content: 原始MD内容

        返回:
            str: 过滤后的内容
        """
        lines = []
        skip = False
        for line in content.split("\n"):
            is_heading = line.startswith("#")
            if is_heading:
                # 检查标题是否包含要排除的关键词
                heading_upper = line.upper().replace(" ", "").replace("#", "")
                skip = any(ex.upper().replace(" ", "") in heading_upper for ex in self.exclude_sections)
            if not skip:
                lines.append(line)
        return "\n".join(lines)

    async def run(self) -> None:
        """异步执行所有文件"""
        md_files: List[Path] = list(self.input_folder.rglob("*.md"))
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

        async def bounded_task(md_file: Path, i: int) -> Tuple[bool, float]:
            async with semaphore:
                return await self._process_single(md_file, i)

        tasks = [bounded_task(f, i) for i, f in enumerate(md_files, 1)]
        await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - self.start_time if self.start_time else 0
        self.log("")
        self.log("=== Batch Completed ===")
        self.log(f"Processed: {self.processed} | Failed: {self.failed} | Success: {self.processed/self.total*100:.1f}%")

    def run_batch(self) -> None:
        """同步入口，启动异步任务"""
        self.start_time = time.time()
        asyncio.run(self.run())
        total_time = time.time() - self.start_time
        self.log(f"Total time: {total_time:.1f}s ({total_time/60:.1f}min)")