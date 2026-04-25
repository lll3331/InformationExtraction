#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/pdf2md.py
批量 PDF → MD，通过 MinerU 转换

【统一参数配置区】
"""

# ---------- YAML 配置路径 ----------
CONFIG_FILE = "config/custom_magnetocaloric.yaml"

# ---------- 运行时强制设置 ----------
SUB_FOLDER = "123"             # 必须设置：处理哪个子文件夹，如 NiMnSn、NiMnIn，None 表示处理所有
# ----------------------------------

# ---------- 运行时覆盖（默认 None，覆盖时生效） ----------
PAPER_DIR = None              # PDF 源文件目录
MD_ZIP_DIR = None             # MinerU 转换结果目录
MD_DIR = None                 # Markdown 输出目录
BATCH_SIZE = None             # 每批 PDF 数量
BATCH_DELAY = None            # 批次间延迟（秒）
# ----------------------------------

import os
os.environ["PYTHONIOENCODING"] = "utf-8"

import sys
import time
import asyncio
from pathlib import Path

# Windows下强制UTF-8输出（由 src/mineru_client.py 统一处理）

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mineru_client import (
    upload_files_to_mineru,
    query_and_download_all_results_async,
    extract_md_from_folders
)
from src.config_loader import ConfigLoader, get_cfg

PROJECT_ROOT = Path(__file__).parent.parent


def resolve_config():
    """解析配置：脚本变量 > yaml"""
    cfg = get_cfg(CONFIG_FILE)

    resolved = {}

    # 路径配置
    resolved["PAPER_DIR"] = PAPER_DIR if PAPER_DIR is not None else PROJECT_ROOT / cfg.get("paths.paper_dir", "paper")
    resolved["MD_ZIP_DIR"] = MD_ZIP_DIR if MD_ZIP_DIR is not None else PROJECT_ROOT / cfg.get("paths.md_zip_dir", "md_zip")
    resolved["MD_DIR"] = MD_DIR if MD_DIR is not None else PROJECT_ROOT / cfg.get("paths.md_dir", "md")

    # 批处理参数
    resolved["BATCH_SIZE"] = BATCH_SIZE if BATCH_SIZE is not None else cfg.get("pdf2md.batch_size", 20)
    resolved["BATCH_DELAY"] = BATCH_DELAY if BATCH_DELAY is not None else cfg.get("pdf2md.batch_delay", 3)

    # 子文件夹参数（强制设置，不从 yaml 读取）
    resolved["SUB_FOLDER"] = SUB_FOLDER

    # MinerU token
    resolved["MINERU_TOKEN"] = cfg.get("mineru.api_token")

    return resolved


def get_sub_folders(paper_dir: Path, sub_folder: str):
    """
    获取要处理的子文件夹列表

    参数:
        paper_dir: paper 目录路径
        sub_folder: 指定子文件夹名称，null 表示处理所有子文件夹

    返回:
        list: 子文件夹路径列表
    """
    if sub_folder:
        # 只处理指定的子文件夹
        target = paper_dir / sub_folder
        if target.exists() and target.is_dir():
            return [target]
        else:
            print(f"[ERROR] 指定子文件夹不存在: {target}")
            return []
    else:
        # 处理所有子文件夹
        sub_folders = [d for d in paper_dir.iterdir() if d.is_dir()]
        return sub_folders


async def process_all_batches(token, pdf_files, zip_dir, batch_size, batch_delay):
    """一次性处理所有批次，统一管理异步"""
    total = len(pdf_files)
    total_batches = (total + batch_size - 1) // batch_size
    all_results = []

    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, total)
        batch = pdf_files[start:end]

        print(f"\n=== Batch {batch_idx + 1}/{total_batches} ({len(batch)} files) ===")

        batch_id = upload_files_to_mineru(token, batch)
        if batch_id is None:
            print(f"[FAIL] Upload batch {batch_idx + 1} failed, skipping")
            continue

        print("Converting...")
        try:
            results = await query_and_download_all_results_async(
                token, batch_id, zip_dir, poll_interval=2
            )
            all_results.extend(results or [])
            print(f"Batch {batch_idx + 1} done")
        except Exception as e:
            print(f"[ERROR] Batch {batch_idx + 1} failed: {e}")

        if batch_idx < total_batches - 1:
            print(f"Waiting {batch_delay}s...")
            await asyncio.sleep(batch_delay)

    return all_results


if __name__ == "__main__":
    cfg = resolve_config()

    paper_dir = cfg["PAPER_DIR"]
    md_zip_dir = cfg["MD_ZIP_DIR"]
    md_dir = cfg["MD_DIR"]
    batch_size = cfg["BATCH_SIZE"]
    batch_delay = cfg["BATCH_DELAY"]
    mineru_token = cfg["MINERU_TOKEN"]
    sub_folder = cfg["SUB_FOLDER"]

    # 获取要处理的子文件夹
    sub_folders = get_sub_folders(paper_dir, sub_folder)
    if not sub_folders:
        print("[ERROR] 没有找到要处理的子文件夹")
        sys.exit(1)

    total_pdf_count = 0
    for sub_dir in sub_folders:
        print(f"\n处理子文件夹: {sub_dir.name}")
        print("=" * 40)

        # 该子文件夹的输出目录
        sub_md_zip_dir = md_zip_dir / sub_dir.name
        sub_md_dir = md_dir / sub_dir.name

        sub_md_zip_dir.mkdir(parents=True, exist_ok=True)
        sub_md_dir.mkdir(parents=True, exist_ok=True)

        # 获取该子文件夹下的 PDF 文件
        pdf_files = list(sub_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"[WARN] No PDF found in {sub_dir}")
            continue

        print(f"Found {len(pdf_files)} PDF files in {sub_dir.name}")
        total_pdf_count += len(pdf_files)

        # Run all batches in single async context
        results = asyncio.run(process_all_batches(mineru_token, pdf_files, sub_md_zip_dir, batch_size, batch_delay))

        # Extract MD files
        print("\n" + "=" * 40)
        print(f"Extracting MD files for {sub_dir.name}...")
        zip_files = list(sub_md_zip_dir.glob("*.zip"))
        print(f"Found {len(zip_files)} zip files")
        extracted = extract_md_from_folders(zip_files, output_dir=sub_md_dir, delete_zip=False)
        print(f"Extracted {len(extracted)} MD files to {sub_md_dir}")

    print(f"\n[FINAL] Total: {total_pdf_count} PDF files processed")