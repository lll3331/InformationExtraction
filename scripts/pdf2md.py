#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/pdf2md.py
批量 PDF → MD，通过 MinerU 转换
"""
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
from utils.config import get_cfg

PROJECT_ROOT = Path(__file__).parent.parent
PAPER_DIR = PROJECT_ROOT / "paper"
MD_ZIP_DIR = PROJECT_ROOT / "md_zip"
MD_DIR = PROJECT_ROOT / "md"

BATCH_SIZE = 20
BATCH_DELAY = 3

cfg = get_cfg()
MINERU_TOKEN = cfg["MinerU"]["API"]

async def process_all_batches(token, pdf_files, zip_dir):
    """一次性处理所有批次，统一管理异步"""
    total = len(pdf_files)
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []

    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total)
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
            print(f"Waiting {BATCH_DELAY}s...")
            await asyncio.sleep(BATCH_DELAY)

    return all_results

if __name__ == "__main__":
    MD_ZIP_DIR.mkdir(parents=True, exist_ok=True)
    MD_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = list(PAPER_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"[ERROR] No PDF found in {PAPER_DIR}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF files")
    print(f"Batching: {BATCH_SIZE} per batch")

    # Run all batches in single async context
    results = asyncio.run(process_all_batches(MINERU_TOKEN, pdf_files, MD_ZIP_DIR))

    # Extract MD files
    print("\n" + "=" * 36)
    print("Extracting MD files...")
    zip_files = list(MD_ZIP_DIR.glob("*.zip"))
    print(f"Found {len(zip_files)} zip files")
    extracted = extract_md_from_folders(zip_files, output_dir=MD_DIR, delete_zip=False)

    print(f"\n[FINAL] Extracted {len(extracted)} MD files to {MD_DIR}")