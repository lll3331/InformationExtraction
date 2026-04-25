#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/render_prompt.py
渲染 Prompt 模板并输出，用于检查最终效果

【统一参数配置区】
"""

# ---------- YAML 配置路径 ----------
CONFIG_FILE = "config/custom_magnetocaloric.yaml"

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_loader import get_cfg

PROJECT_ROOT = Path(__file__).parent.parent


def resolve_config():
    """解析配置：脚本变量 > yaml"""
    cfg = get_cfg(CONFIG_FILE)
    return {
        "SCHEMA_FILE": cfg.get("md2json.schema_file"),
        "PROMPT_FILE": cfg.get("md2json.prompt_file"),
    }


def render_prompt(prompt_template_path: Path, schema: dict) -> str:
    """渲染 Prompt 模板"""
    with open(prompt_template_path, "r", encoding="utf-8") as f:
        template = f.read()

    fields_list = "\n".join([
        f"{i+1}. {f['name']}: {f['description']}"
        for i, f in enumerate(schema.get("fields", []))
    ])

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


if __name__ == "__main__":
    cfg = resolve_config()
    schema_path = PROJECT_ROOT / cfg["SCHEMA_FILE"]
    prompt_path = PROJECT_ROOT / cfg["PROMPT_FILE"]

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    rendered = render_prompt(prompt_path, schema)

    print("=" * 60)
    print(f"Schema: {cfg['SCHEMA_FILE']}")
    print(f"Prompt: {cfg['PROMPT_FILE']}")
    print("=" * 60)
    print(rendered)
