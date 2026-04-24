#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/json2csv.py
合并 json/ 目录下所有 JSON 为 result.csv
"""
from pathlib import Path
import sys
import json
import csv

PROJECT_ROOT = Path(__file__).parent.parent
JSON_DIR = PROJECT_ROOT / "json"
OUTPUT_CSV = PROJECT_ROOT / "result.csv"

# CSV 字段顺序
FIELD_NAMES = [
    "alloy_composition",
    "sample_preparation",
    "max_magnetic_entropy",
    "temperature",
    "magnetic_field",
    "source_pdf"
]

def json_files_to_csv(json_dir: Path, output_csv: Path) -> None:
    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        print(f"[ERROR] No .json found in {json_dir}")
        sys.exit(1)

    print(f"Found {len(json_files)} JSON files")

    rows = []
    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)

            # data 可能是 {"data": [...]} 或直接是列表
            records = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(records, list):
                records = [records]

            for rec in records:
                row = {k: rec.get(k, "") for k in FIELD_NAMES}
                rows.append(row)

        except Exception as e:
            print(f"[WARN] Failed to read {jf.name}: {e}")
            continue

    if not rows:
        print("[ERROR] No valid records found")
        sys.exit(1)

    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Wrote {len(rows)} rows to {output_csv}")

if __name__ == "__main__":
    json_files_to_csv(JSON_DIR, OUTPUT_CSV)