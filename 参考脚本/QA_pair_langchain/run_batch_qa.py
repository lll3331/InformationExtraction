#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件名: run_batch_qa.py
功能: 使用LangChain批量生成问答对的入口脚本
作者: LiuYZ
创建日期: 2026-01-01
版本: 1.0.0
"""

import sys
from pathlib import Path

# 获取项目路径
current_pyfile = Path(__file__)
current_dir = current_pyfile.parent
Project_folder = current_pyfile.parents[2]

# 添加 src 目录到路径（必须在导入项目模块之前）
sys.path.insert(0, str(Project_folder / 'src'))

from langchain_openai import ChatOpenAI

from batch_qa_extractor import BatchQAExtractorLangChain
from utils.config import load_config


def main() -> None:
    """
    主函数：配置并运行批量问答对提取。
    """
    # 配置输入输出路径
    input_folder = Project_folder / r'outputs/QA_pair/3/md_extracted'
    output_folder = input_folder.parent / (input_folder.stem + '_answer_json_langchain')
    output_folder.mkdir(exist_ok=True, parents=True)
    prompt_path = Project_folder / r'config/prompt.md'

    # 读取配置
    cfg = load_config("config/langchain_config.yaml")

    # ============ 选择AI模型 ============
    # Qwen3-max
    url = cfg['cloud_AI']['qwen3']['url']
    api_key = cfg['cloud_AI']['qwen3']['keys']
    model = 'qwen3-max'

    # BLM
    # url = cfg['cloud_AI']['bigmodel']['url']
    # api_key = cfg['cloud_AI']['bigmodel']['keys']
    # model = 'glm-4.5-air'

    # Deepseek
    # url = cfg['cloud_AI']['deepseek']['url']
    # api_key = cfg['cloud_AI']['deepseek']['keys']
    # model = 'deepseek-chat'

    # local
    # url = cfg['local_AI']['base_url']
    # api_key = 'not-needed'  # 本地模型通常不需要 API key
    # model = cfg['local_AI']['chat_model']


    # ============ 创建 LangChain LLM ============
    llm = ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        openai_api_base=url,
        temperature=0.7,
        request_timeout=300,  # 5分钟超时
    )

    # 读取系统提示词
    with open(prompt_path, 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    # 创建批量处理器并运行
    extractor = BatchQAExtractorLangChain(
        input_folder=input_folder,
        output_folder=output_folder,
        llm=llm,
        system_prompt=system_prompt,
        max_concurrent=10
    )
    extractor.run_batch_processing()


if __name__ == '__main__':
    main()
