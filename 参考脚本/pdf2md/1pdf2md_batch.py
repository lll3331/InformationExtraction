#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件名: 1pdf2md_batch.py
功能: 用于批量的MinerU转换，支持分批上传处理
作者: LiuYZ, 
创建日期: 2025-11-14
版本: 2.0.0 - 添加分批上传功能
"""
from pathlib import Path
import time

from utils.file_path import find_files_with_suffix
from utils.config import get_cfg
from paperProcessing.pdf2md_mineru import upload_files_to_mineru, query_and_download_all_results_async
import asyncio

pdf_dir = Path(r'D:\0AAA\UV\RAG_search\output\磁热材料\1\pdf')
output_dir = Path(r'D:\0AAA\UV\RAG_search\output\磁热材料\1\md_zip')
output_dir.mkdir(exist_ok=True)

cfg = get_cfg()
MinerU_api = cfg['MinerU']['API']

# 分批处理参数
BATCH_SIZE = 20  # 每批处理的文件数量
BATCH_DELAY = 3  # 批次之间的延迟时间（秒）

# 查找pdf文件
all_files = find_files_with_suffix(pdf_dir,['.pdf'],1)
print(f'共{len(all_files)}个文件')

# 分批处理
total_batches = (len(all_files) + BATCH_SIZE - 1) // BATCH_SIZE
print(f'将分为 {total_batches} 批处理，每批最多 {BATCH_SIZE} 个文件')

all_results = []

for batch_idx in range(total_batches):
    start_idx = batch_idx * BATCH_SIZE
    end_idx = min(start_idx + BATCH_SIZE, len(all_files))
    batch_files = all_files[start_idx:end_idx]
    
    print(f'\n处理第 {batch_idx + 1}/{total_batches} 批，包含 {len(batch_files)} 个文件')
    
    # 上传当前批次的文件
    batch_id = upload_files_to_mineru(MinerU_api, batch_files)
    
    if batch_id is None:
        print(f'第 {batch_idx + 1} 批上传失败，跳过此批次')
        continue
    
    # 开始pdf2md转换
    print('开始转换当前批次')
    print("~"*30)
    
    try:
        result_list = asyncio.run(
            query_and_download_all_results_async(
                MinerU_api,
                batch_id,
                output_dir,
                poll_interval=2
            )
        )
        all_results.extend(result_list)
        print(f'第 {batch_idx + 1} 批转换完成')
    except Exception as e:
        print(f'第 {batch_idx + 1} 批转换过程中出错: {e}')
        continue
    
    # 如果不是最后一批，添加延迟
    if batch_idx < total_batches - 1:
        print(f'等待 {BATCH_DELAY} 秒后处理下一批...')
        time.sleep(BATCH_DELAY)

print('\n所有批次处理完成！')
print(f'总共处理了 {len(all_results)} 个文件')

