import asyncio
import aiohttp
import time
from pathlib import Path
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

from tools.tool_md数据处理 import extract_content


def test_prompt_single_file(md_file_path, output_txt_path, ai_ass, system_prompt):
    """
    为BatchQAExtractor做前期的prompt测试
    处理单个MD文件并输出到指定txt路径
    
    Args:
        md_file_path (str): 输入的MD文件路径
        output_txt_path (str): 输出的txt文件路径
        ai_ass: AI助手实例
        system_prompt (str): 系统提示词
    
    Returns:
        bool: 处理是否成功
    """
    try:
        # 提取MD文件内容
        filtered_content = extract_content(md_file_path)
        if filtered_content.startswith('错误：'):
            print(f"提取内容失败: {filtered_content}")
            return False
        
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"**Paper content**\n{filtered_content}"}
        ]
        
        # 同步调用AI生成问答对
        response = ai_ass.generate(messages)
        
        # 确保输出目录存在
        output_path = Path(output_txt_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存结果
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write(response)
        
        print(f"处理完成: {md_file_path} -> {output_txt_path}")
        return True
        
    except Exception as e:
        print(f"处理失败: {md_file_path}, 错误: {str(e)}")
        return False


def setup_logger(log_path):
    """
    创建 logger：
    - INFO 以上写入文件
    - INFO 以上打印到控制台
    - 自动滚动日志：每个 5MB，保留 3 份
    """
    logger = logging.getLogger("BatchQAExtractor")
    logger.setLevel(logging.INFO)

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



class BatchQAExtractor:
    def __init__(self, input_folder, output_folder, ai_ass, system_prompt, max_concurrent=5):
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.ai_ass = ai_ass
        self.max_concurrent = max_concurrent
        
        # 创建输出文件夹
        self.output_folder.mkdir(parents=True, exist_ok=True)

        # 创建日志记录器
        self.log_path = self.output_folder / "processing_log.txt"
        self.logger = setup_logger(self.log_path)

        # # 初始化AI助手
        # self.ai_ass = AI_Assistant()
        # self.ai_ass.headers = {'Authorization': f"Bearer {api_key}"}
        # self.ai_ass.url_generate = 'https://api.deepseek.com/chat/completions'
        # self.ai_ass.model_generate = 'deepseek-reasoner'
        
        # 系统提示词
        self.system_prompt = system_prompt
        
        # 统计信息
        self.processed_count = 0
        self.failed_count = 0
        self.total_files = 0
        self.start_time = None

    def log_message(self, message, level="info"):
        """统一日志方法（替代 print + 手写文件）"""
        if level == "error":
            self.logger.error(message)
        elif level == "warning":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    async def process_single_file(self, session, md_file, file_index):
        """处理单个MD文件"""
        file_start_time = time.time()
        file_start_str = datetime.now().strftime("%H:%M:%S")
        
        try:
            # 提取MD文件内容
            filtered_content = extract_content(str(md_file))
            if filtered_content.startswith('错误：'):
                raise Exception(filtered_content)
            
            # 构建消息
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"**Paper content**\n{filtered_content}"}
            ]
            
            # 异步调用AI生成问答对
            response = await self.ai_ass.async_generate(session, messages)
            
            # 保存结果
            output_file = self.output_folder / f"{md_file.stem}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(response)
            
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

    async def process_files_async(self, md_files):
        """异步处理所有MD文件"""

        # 输出基本信息
        start_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_message("=== 批量问答对提取开始 ===")
        self.log_message(f"开始时间: {start_time_str}")
        self.log_message(f"输入文件夹: {self.input_folder}")
        self.log_message(f"目标文件夹: {self.output_folder}")
        self.log_message(f"并发数量: {self.max_concurrent}")
        self.log_message(f"总文件数: {self.total_files}")
        self.log_message("")
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def bounded_process(session, md_file, file_index):
            async with semaphore:
                return await self.process_single_file(session, md_file, file_index)
        
        # aiohttp 会话
        timeout = aiohttp.ClientTimeout(total=60*5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            tasks = []
            for i, md_file in enumerate(md_files, 1):
                task = bounded_process(session, md_file, i)
                tasks.append(task)
            
            await asyncio.gather(*tasks, return_exceptions=True)

    def run_batch_processing(self):
        """运行批量处理"""

        # 获取所有 MD 文件
        md_files = list(self.input_folder.rglob("*.md"))
        self.total_files = len(md_files)
        
        if self.total_files == 0:
            self.log_message(f"错误: 在文件夹 {self.input_folder} 中未找到任何MD文件", level="error")
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
        self.log_message(f"处理成功率: {self.processed_count/self.total_files*100:.1f}%")
