#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/md2json.py
批量 MD → JSON，通过 LLM with_structured_output 强制输出
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_openai import ChatOpenAI
from src.llm_extractor import BatchExtractor
from utils.config import get_cfg

# ========== 配置 ==========
PROJECT_ROOT = Path(__file__).parent.parent
MD_DIR = PROJECT_ROOT / "md"
JSON_DIR = PROJECT_ROOT / "json"

cfg = get_cfg()

# LLM 配置
llm = ChatOpenAI(
    model=cfg["qwen3"]["models"][0],
    api_key=cfg["qwen3"]["keys"],
    base_url=cfg["qwen3"]["url"],
    temperature=0.1
)

# System prompt：引导 LLM 提取6个字段
SYSTEM_PROMPT = """你是一个磁热材料文献信息提取专家。
请从提供的论文内容中提取以下6个字段的信息：

1. alloy_composition: 合金化学成分（保留原始表述，如 Ni50Mn35Sn15 或 Ni40Co10Mn40Sn10）
2. sample_preparation: 样品制备方法（简要描述制备工艺，如 感应熔炼+区熔退火+水淬）
3. max_magnetic_entropy: 最大磁熵变数值及单位（如 18.5 J/kg·K 或 12.8 J kg^-1 K^-1）
4. temperature: 最大磁熵变对应的温度（如 305 K 或 30°C）
5. magnetic_field: 测量时外加磁场（如 5 T 或 50 kOe）
6. source_pdf: 来源PDF的文件名（从输入文件路径中提取）

要求：
- 只输出数据，不要有其他解释
- 数值尽量保留原文格式
- 如果某字段在文中未提及，填 "未提及"
- 合金成分应包含主要元素及比例信息

请以JSON格式输出，包含上述6个字段。"""

MAX_CONCURRENT = 10

# ========== 主流程 ==========
if __name__ == "__main__":
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    md_files = list(MD_DIR.glob("*.md"))
    if not md_files:
        print(f"[ERROR] No .md files found in {MD_DIR}")
        sys.exit(1)

    print(f"Found {len(md_files)} MD files")
    print(f"Max concurrent: {MAX_CONCURRENT}")

    extractor = BatchExtractor(
        input_folder=MD_DIR,
        output_folder=JSON_DIR,
        llm=llm,
        system_prompt=SYSTEM_PROMPT,
        max_concurrent=MAX_CONCURRENT
    )

    extractor.run_batch()
    print(f"\n[FINAL] JSON files saved to {JSON_DIR}")