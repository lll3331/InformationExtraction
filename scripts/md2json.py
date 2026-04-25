#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/md2json.py
批量 MD → JSON，通过 LLM with_structured_output 强制输出

【统一参数配置区】
"""

# ---------- YAML 配置路径 ----------
CONFIG_FILE = "config/custom_magnetocaloric.yaml"

# ---------- 运行时强制设置 ----------
SUB_FOLDER = "123"             # 必须设置：处理哪个子文件夹，如 NiMnSn、NiMnIn，None 表示处理所有
# ----------------------------------

# ---------- 运行时覆盖（默认 None，覆盖时生效） ----------
MD_DIR = None                 # Markdown 输入目录
JSON_DIR = None               # JSON 输出目录
SCHEMA_FILE = None            # Schema 文件路径
PROMPT_FILE = None            # Prompt 模板文件路径
TEMPERATURE = None            # LLM 温度
MAX_CONCURRENT = None         # 最大并发数
EXCLUDE_SECTIONS = None       # 要过滤的章节标题关键词列表
# ----------------------------------

import os
import sys
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_openai import ChatOpenAI

from src.config_loader import get_cfg
from src.pydantic_generator import load_schema_and_generate_models, get_schema_field_names
from src.llm_extractor import BatchExtractor

PROJECT_ROOT = Path(__file__).parent.parent


def resolve_config():
    """解析配置：脚本变量 > yaml"""
    cfg = get_cfg(CONFIG_FILE)

    resolved = {}

    # 路径配置
    resolved["MD_DIR"] = MD_DIR if MD_DIR is not None else PROJECT_ROOT / cfg.get("paths.md_dir", "md")
    resolved["JSON_DIR"] = JSON_DIR if JSON_DIR is not None else PROJECT_ROOT / cfg.get("paths.json_dir", "json")

    # Schema 和 Prompt
    resolved["SCHEMA_FILE"] = SCHEMA_FILE if SCHEMA_FILE is not None else cfg.get("md2json.schema_file")
    resolved["PROMPT_FILE"] = PROMPT_FILE if PROMPT_FILE is not None else cfg.get("md2json.prompt_file")

    # LLM 参数
    resolved["TEMPERATURE"] = TEMPERATURE if TEMPERATURE is not None else cfg.get("md2json.temperature", 0.1)
    resolved["MAX_CONCURRENT"] = MAX_CONCURRENT if MAX_CONCURRENT is not None else cfg.get("md2json.max_concurrent", 10)

    # 排除章节
    resolved["EXCLUDE_SECTIONS"] = EXCLUDE_SECTIONS if EXCLUDE_SECTIONS is not None else cfg.get("md2json.exclude_sections", [])

    # 子文件夹参数（强制设置，不从 yaml 读取）
    resolved["SUB_FOLDER"] = SUB_FOLDER

    # LLM 配置
    resolved["LLM_MODEL"] = cfg.get("llm.model", "qwen3-max")
    resolved["LLM_API_KEY"] = cfg.get("llm.api_key")
    resolved["LLM_BASE_URL"] = cfg.get("llm.base_url")

    return resolved


def get_sub_folders(md_dir: Path, sub_folder: str):
    """
    获取要处理的子文件夹列表

    参数:
        md_dir: md 目录路径
        sub_folder: 指定子文件夹名称，null 表示处理所有子文件夹

    返回:
        list: 子文件夹路径列表
    """
    if sub_folder:
        target = md_dir / sub_folder
        if target.exists() and target.is_dir():
            return [target]
        else:
            print(f"[ERROR] 指定子文件夹不存在: {target}")
            return []
    else:
        sub_folders = [d for d in md_dir.iterdir() if d.is_dir()]
        return sub_folders


def render_prompt(prompt_template_path: Path, schema: dict) -> str:
    """
    渲染 Prompt 模板，填入 schema 信息

    参数:
        prompt_template_path: Prompt 模板文件路径
        schema: Schema 字典

    返回:
        str: 渲染后的 prompt
    """
    with open(prompt_template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # 生成字段列表
    fields_list = "\n".join([
        f"{i+1}. {f['name']}: {f['description']}"
        for i, f in enumerate(schema.get("fields", []))
    ])

    # 生成字段说明
    field_descriptions = "\n".join([
        f"- **{f['name']}**: {f['description']}" + (f"（示例: {f.get('example', 'N/A')}）" if f.get('example') else "")
        for f in schema.get("fields", [])
    ])

    replacements = {
        "{domain}": schema.get("description", "通用"),
        "{fields_list}": fields_list,
        "{field_descriptions}": field_descriptions,
    }

    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    return result


def main() -> None:
    """主流程"""
    cfg = resolve_config()

    md_dir = cfg["MD_DIR"]
    json_dir = cfg["JSON_DIR"]
    schema_file = cfg["SCHEMA_FILE"]
    prompt_file = cfg["PROMPT_FILE"]
    temperature = cfg["TEMPERATURE"]
    max_concurrent = cfg["MAX_CONCURRENT"]
    exclude_sections = cfg["EXCLUDE_SECTIONS"]
    sub_folder = cfg["SUB_FOLDER"]
    llm_model = cfg["LLM_MODEL"]
    llm_api_key = cfg["LLM_API_KEY"]
    llm_base_url = cfg["LLM_BASE_URL"]

    # 加载 Schema 并生成 Pydantic 模型
    schema_path = PROJECT_ROOT / schema_file
    _, list_model = load_schema_and_generate_models(schema_path)

    # 加载 schema 字典用于渲染 prompt
    import json
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_dict = json.load(f)

    # 渲染 Prompt
    prompt_path = PROJECT_ROOT / prompt_file
    system_prompt = render_prompt(prompt_path, schema_dict)

    # 初始化 LLM
    llm = ChatOpenAI(
        model=llm_model,
        api_key=llm_api_key,
        base_url=llm_base_url,
        temperature=temperature
    )

    # 获取要处理的子文件夹
    sub_folders = get_sub_folders(md_dir, sub_folder)
    if not sub_folders:
        print("[ERROR] 没有找到要处理的子文件夹")
        sys.exit(1)

    total_md_count = 0
    for sub_dir in sub_folders:
        print(f"\n处理子文件夹: {sub_dir.name}")
        print("=" * 40)

        sub_md_dir = sub_dir
        sub_json_dir = json_dir / sub_dir.name

        sub_json_dir.mkdir(parents=True, exist_ok=True)

        md_files = list(sub_md_dir.glob("*.md"))
        if not md_files:
            print(f"[WARN] No .md files found in {sub_md_dir}")
            continue

        print(f"Found {len(md_files)} MD files")
        print(f"Schema: {schema_path.name}")
        print(f"Prompt: {prompt_path.name}")
        print(f"Max concurrent: {max_concurrent}")

        total_md_count += len(md_files)

        # 创建提取器
        extractor = BatchExtractor(
            input_folder=sub_md_dir,
            output_folder=sub_json_dir,
            llm=llm,
            system_prompt=system_prompt,
            output_model=list_model,
            max_concurrent=max_concurrent,
            exclude_sections=exclude_sections
        )

        extractor.run_batch()
        print(f"[OK] JSON files saved to {sub_json_dir}")

    print(f"\n[FINAL] Total: {total_md_count} MD files processed")


if __name__ == "__main__":
    main()