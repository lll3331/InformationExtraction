#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/pdf2md.py
批量 PDF → MD，通过 MinerU 转换

【统一参数配置区】
"""

# ---------- YAML 配置路径 ----------
CONFIG_FILE = "config/custom_magnetocaloric.yaml"

# ---------- 运行时覆盖（默认 None，覆盖时生效）----------
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

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mineru_client import (
    upload_files_to_mineru,
    query_and_download_all_results_async,
    extract_md_from_folders
)
from src.config_loader import ConfigLoader, get_cfg

PROJECT_ROOT = Path(__file__).parent.parent


def resolve_config():
    """解析配置：脚本变量为 None 时用 yaml 的值"""
    cfg = get_cfg(CONFIG_FILE)

    resolved = {}

    # 路径配置
    resolved["PAPER_DIR"] = PAPER_DIR if PAPER_DIR is not None else PROJECT_ROOT / cfg.get("paths.paper_dir", "paper")
    resolved["MD_ZIP_DIR"] = MD_ZIP_DIR if MD_ZIP_DIR is not None else PROJECT_ROOT / cfg.get("paths.md_zip_dir", "md_zip")
    resolved["MD_DIR"] = MD_DIR if MD_DIR is not None else PROJECT_ROOT / cfg.get("paths.md_dir", "md")

    # 批处理参数
    resolved["BATCH_SIZE"] = BATCH_SIZE if BATCH_SIZE is not None else cfg.get("pdf2md.batch_size", 20)
    resolved["BATCH_DELAY"] = BATCH_DELAY if BATCH_DELAY is not None else cfg.get("pdf2md.batch_delay", 3)

    # MinerU token
    resolved["MINERU_TOKEN"] = cfg.get("mineru.api_token")

    return resolved


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

    md_zip_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(paper_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"[ERROR] No PDF found in {paper_dir}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF files")
    print(f"Batching: {batch_size} per batch")

    # Run all batches in single async context
    results = asyncio.run(process_all_batches(mineru_token, pdf_files, md_zip_dir, batch_size, batch_delay))

    # Extract MD files
    print("\n" + "=" * 36)
    print("Extracting MD files...")
    zip_files = list(md_zip_dir.glob("*.zip"))
    print(f"Found {len(zip_files)} zip files")
    extracted = extract_md_from_folders(zip_files, output_dir=md_dir, delete_zip=False)

    print(f"\n[FINAL] Extracted {len(extracted)} MD files to {md_dir}")