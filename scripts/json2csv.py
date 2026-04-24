#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/json2csv.py
合并 json/ 目录下所有 JSON 为 result.csv

【统一参数配置区】
"""

# ---------- YAML 配置路径 ----------
CONFIG_FILE = "config/custom_magnetocaloric.yaml"

# ---------- 运行时覆盖（默认 None，覆盖时生效）----------
JSON_DIR = None               # JSON 输入目录
RESULT_CSV = None             # CSV 输出路径
SCHEMA_FILE = None            # Schema 文件路径（用于确定 CSV 列顺序）
# ----------------------------------

import os
import sys
import json
import csv
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_loader import get_cfg
from src.pydantic_generator import get_schema_field_names

PROJECT_ROOT = Path(__file__).parent.parent


def resolve_config():
    """解析配置：脚本变量为 None 时用 yaml 的值"""
    cfg = get_cfg(CONFIG_FILE)

    resolved = {}

    # 路径配置
    resolved["JSON_DIR"] = JSON_DIR if JSON_DIR is not None else PROJECT_ROOT / cfg.get("paths.json_dir", "json")
    resolved["RESULT_CSV"] = RESULT_CSV if RESULT_CSV is not None else PROJECT_ROOT / cfg.get("paths.result_csv", "result.csv")

    # Schema 文件
    resolved["SCHEMA_FILE"] = SCHEMA_FILE if SCHEMA_FILE is not None else cfg.get("md2json.schema_file")

    return resolved


def json_files_to_csv(json_dir: Path, output_csv: Path, field_names: List[str]) -> None:
    """
    将json目录下的所有JSON文件合并为一个CSV文件

    参数:
        json_dir: JSON文件所在目录
        output_csv: 输出CSV文件路径
        field_names: CSV 字段名列表
    """
    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        print(f"[ERROR] No .json found in {json_dir}")
        sys.exit(1)

    print(f"Found {len(json_files)} JSON files")

    rows: List[dict] = []
    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)

            # data 可能是 {"data": [...]} 或直接是列表
            records = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(records, list):
                records = [records]

            for rec in records:
                row = {k: rec.get(k, "") for k in field_names}
                rows.append(row)

        except Exception as e:
            print(f"[WARN] Failed to read {jf.name}: {e}")
            continue

    if not rows:
        print("[ERROR] No valid records found")
        sys.exit(1)

    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Wrote {len(rows)} rows to {output_csv}")


def main() -> None:
    """主流程"""
    cfg = resolve_config()

    json_dir = cfg["JSON_DIR"]
    result_csv = cfg["RESULT_CSV"]
    schema_file = cfg["SCHEMA_FILE"]

    # 从 Schema 获取字段顺序
    schema_path = PROJECT_ROOT / schema_file
    field_names = get_schema_field_names(schema_path)

    json_files_to_csv(json_dir, result_csv, field_names)


if __name__ == "__main__":
    main()