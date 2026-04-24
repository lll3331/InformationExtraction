#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件名: batch_qa_extractor.py
功能: 使用LangChain批量生成问答对（异步并行版本）
作者: LiuYZ
创建日期: 2026-01-01
版本: 1.0.0
"""

import asyncio
import time
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple, Any, Literal
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

from tools.tool_md数据处理 import extract_content


class QAPair(BaseModel):
    """单条问答对模型"""
    question: str = Field(description="问题文本（中文）")
    answer: str = Field(description="基于论文内容抽象得到的准确回答（中文）")
    question_type: Literal["定义", "原理", "方法", "比较", "应用"] = Field(description="问题类型")


class QAPairList(BaseModel):
    """问答对列表模型"""
    qa_pairs: List[QAPair] = Field(description="生成的问答对列表")


def setup_logger(log_path: Path) -> logging.Logger:
    """
    创建 logger：
    - INFO 以上写入文件
    - INFO 以上打印到控制台
    - 自动滚动日志：每个 5MB，保留 3 份

    Args:
        log_path: 日志文件路径

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger("BatchQAExtractorLangChain")
    logger.setLevel(logging.INFO)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件 Handler（带滚动日志）
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


class BatchQAExtractorLangChain:
    """
    使用LangChain进行批量问答对提取的类。
    
    支持异步并行处理多个MD文件，使用信号量控制并发数量。
    """
    
    def __init__(
        self,
        input_folder: Path,
        output_folder: Path,
        llm: BaseChatModel,
        system_prompt: str,
        max_concurrent: int = 5
    ) -> None:
        """
        初始化批量问答对提取器。

        Args:
            input_folder: 输入MD文件所在的文件夹路径
            output_folder: 输出结果保存的文件夹路径
            llm: LangChain的聊天模型实例
            system_prompt: 系统提示词
            max_concurrent: 最大并发数量，默认为5
        """
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.llm = llm
        self.system_prompt = system_prompt
        self.max_concurrent = max_concurrent

        # 绑定结构化输出模型
        self.structured_llm = self.llm.with_structured_output(QAPairList)
        
        # 创建输出文件夹
        self.output_folder.mkdir(parents=True, exist_ok=True)

        # 创建日志记录器
        self.log_path = self.output_folder / "processing_log.txt"
        self.logger = setup_logger(self.log_path)
        
        # 统计信息
        self.processed_count = 0
        self.failed_count = 0
        self.total_files = 0
        self.start_time: Optional[float] = None

    def log_message(self, message: str, level: str = "info") -> None:
        """
        统一日志方法。

        Args:
            message: 日志消息内容
            level: 日志级别，可选 'info', 'warning', 'error'
        """
        if level == "error":
            self.logger.error(message)
        elif level == "warning":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    async def process_single_file(
        self,
        md_file: Path,
        file_index: int
    ) -> Tuple[bool, float]:
        """
        处理单个MD文件。

        Args:
            md_file: MD文件路径
            file_index: 文件在处理队列中的索引

        Returns:
            Tuple[bool, float]: (处理是否成功, 处理耗时)
        """
        file_start_time = time.time()
        file_start_str = datetime.now().strftime("%H:%M:%S")
        
        try:
            # 提取MD文件内容
            filtered_content = extract_content(str(md_file))
            if filtered_content.startswith('错误：'):
                raise Exception(filtered_content)
            
            # 构建消息
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=f"**Paper content**\n{filtered_content}")
            ]
            
            # 异步调用AI生成结构化问答对
            response = await self.structured_llm.ainvoke(messages)
            
            # 保存结果为 JSON 格式
            output_file = self.output_folder / f"{md_file.stem}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                if isinstance(response, QAPairList):
                    json.dump(response.model_dump(), f, ensure_ascii=False, indent=2)
                else:
                    # 兼容性处理
                    json.dump(response, f, ensure_ascii=False, indent=2)
            
            # 计算处理时间
            file_process_time = time.time() - file_start_time
            
            # 更新统计
            self.processed_count += 1
            
            # 输出进度
            progress_msg = (
                f"[{file_index}/{self.total_files}] 处理完成: {md_file.name}\n"
                f"开始时间: {file_start_str} | 处理时间: {file_process_time:.1f}秒 | "
                f"保存到: {output_file.name}"
            )
            self.log_message(progress_msg)
            
            return True, file_process_time
            
        except Exception as e:
            # 计算处理时间
            file_process_time = time.time() - file_start_time

            # 更新统计
            self.failed_count += 1
            
            # 输出错误信息
            error_msg = (
                f"[{file_index}/{self.total_files}] 处理失败: {md_file.name}\n"
                f"开始时间: {file_start_str} | 处理时间: {file_process_time:.1f}秒 | "
                f"错误: {str(e)}"
            )
            self.log_message(error_msg, level="error")
            
            return False, file_process_time

    async def process_files_async(self, md_files: List[Path]) -> None:
        """
        异步处理所有MD文件。

        Args:
            md_files: 待处理的MD文件路径列表
        """
        # 输出基本信息
        start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_message("=== 批量问答对提取开始 (LangChain 版本) ===")
        self.log_message(f"开始时间: {start_time_str}")
        self.log_message(f"输入文件夹: {self.input_folder}")
        self.log_message(f"目标文件夹: {self.output_folder}")
        self.log_message(f"并发数量: {self.max_concurrent}")
        self.log_message(f"总文件数: {self.total_files}")
        self.log_message("")
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def bounded_process(md_file: Path, file_index: int) -> Tuple[bool, float]:
            async with semaphore:
                return await self.process_single_file(md_file, file_index)
        
        # 创建所有任务
        tasks = [
            bounded_process(md_file, i)
            for i, md_file in enumerate(md_files, 1)
        ]
        
        # 并行执行所有任务
        await asyncio.gather(*tasks, return_exceptions=True)

    def run_batch_processing(self) -> None:
        """
        运行批量处理。
        
        此方法是主入口，会扫描输入文件夹中的所有MD文件并进行批量处理。
        """
        # 获取所有 MD 文件
        md_files = list(self.input_folder.rglob("*.md"))
        self.total_files = len(md_files)
        
        if self.total_files == 0:
            self.log_message(
                f"错误: 在文件夹 {self.input_folder} 中未找到任何MD文件",
                level="error"
            )
            return
        
        # 开始计时
        self.start_time = time.time()
        
        # 异步处理
        asyncio.run(self.process_files_async(md_files))
        
        # 计算总时间
        total_time = time.time() - self.start_time
        
        # 输出总结
        self.log_message("")
        self.log_message("=== 批量处理完成 ===")
        self.log_message(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log_message(f"总处理时间: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")
        self.log_message(f"成功处理: {self.processed_count}个文件")
        self.log_message(f"失败文件: {self.failed_count}个")
        if self.total_files > 0:
            self.log_message(f"处理成功率: {self.processed_count/self.total_files*100:.1f}%")
