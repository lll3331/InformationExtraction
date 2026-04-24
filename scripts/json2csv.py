#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/json2csv.py
合并 json/ 目录下所有 JSON 为 result.csv

【统一参数配置区】
"""

# ---------- YAML 配置路径 ----------
CONFIG_FILE = "config/custom_magnetocaloric.yaml"

# ---------- 运行时覆盖（默认 None，覆盖时生效） ----------
JSON_DIR = None               # JSON 输入目录
RESULTS_DIR = None            # CSV 输出目录
SCHEMA_FILE = None            # Schema 文件路径（用于确定 CSV 列顺序）
SUB_FOLDER = None             # 子文件夹名称，null 表示汇总所有子文件夹
# ----------------------------------

import os
import sys
import json
import csv
import argparse
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_loader import get_cfg
from src.pydantic_generator import get_schema_field_names

PROJECT_ROOT = Path(__file__).parent.parent


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="JSON → CSV 合并")
    parser.add_argument("--sub-folder", "-s", type=str, default=None,
                        help="指定子文件夹名称，如 NiMnIn")
    return parser.parse_args()


def resolve_config(sub_folder_cmd: str = None):
    """解析配置：命令行 > 脚本变量 > yaml"""
    cfg = get_cfg(CONFIG_FILE)

    resolved = {}

    # 路径配置
    resolved["JSON_DIR"] = JSON_DIR if JSON_DIR is not None else PROJECT_ROOT / cfg.get("paths.json_dir", "json")
    resolved["RESULTS_DIR"] = RESULTS_DIR if RESULTS_DIR is not None else PROJECT_ROOT / cfg.get("paths.results_dir", "results")

    # Schema 文件
    resolved["SCHEMA_FILE"] = SCHEMA_FILE if SCHEMA_FILE is not None else cfg.get("md2json.schema_file")

    # 子文件夹参数：命令行 > 脚本变量 > yaml
    if sub_folder_cmd:
        resolved["SUB_FOLDER"] = sub_folder_cmd
    elif SUB_FOLDER is not None:
        resolved["SUB_FOLDER"] = SUB_FOLDER
    else:
        resolved["SUB_FOLDER"] = cfg.get("json2csv.sub_folder")

    return resolved


def get_sub_folders(json_dir: Path, sub_folder: str):
    """
    获取要处理的子文件夹列表

    参数:
        json_dir: json 目录路径
        sub_folder: 指定子文件夹名称，null 表示处理所有子文件夹

    返回:
        list: 子文件夹路径列表
    """
    if sub_folder:
        target = json_dir / sub_folder
        if target.exists() and target.is_dir():
            return [target]
        else:
            print(f"[ERROR] 指定子文件夹不存在: {target}")
            return []
    else:
        sub_folders = [d for d in json_dir.iterdir() if d.is_dir()]
        return sub_folders


def json_files_to_csv(json_dir: Path, output_csv: Path, field_names: List[str]) -> int:
    """
    将json目录下的所有JSON文件合并为一个CSV文件

    参数:
        json_dir: JSON文件所在目录
        output_csv: 输出CSV文件路径
        field_names: CSV 字段名列表

    返回:
        int: 处理的记录数
    """
    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        print(f"[WARN] No .json found in {json_dir}")
        return 0

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
        print(f"[WARN] No valid records found in {json_dir}")
        return 0

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Wrote {len(rows)} rows to {output_csv}")
    return len(rows)


def main() -> None:
    """主流程"""
    args = parse_args()
    cfg = resolve_config(args.sub_folder)

    json_dir = cfg["JSON_DIR"]
    results_dir = cfg["RESULTS_DIR"]
    schema_file = cfg["SCHEMA_FILE"]
    sub_folder = cfg["SUB_FOLDER"]

    # 从 Schema 获取字段顺序
    schema_path = PROJECT_ROOT / schema_file
    field_names = get_schema_field_names(schema_path)

    # 获取要处理的子文件夹
    sub_folders = get_sub_folders(json_dir, sub_folder)
    if not sub_folders:
        print("[ERROR] 没有找到要处理的子文件夹")
        sys.exit(1)

    total_records = 0
    for sub_dir in sub_folders:
        print(f"\n处理子文件夹: {sub_dir.name}")
        print("=" * 40)

        sub_json_dir = sub_dir
        output_csv = results_dir / f"{sub_dir.name}.csv"

        record_count = json_files_to_csv(sub_json_dir, output_csv, field_names)
        total_records += record_count

    print(f"\n[FINAL] Total: {total_records} records written to {results_dir}")


if __name__ == "__main__":
    main()