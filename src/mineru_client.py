"""MinerU API 客户端模块"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Windows下强制UTF-8输出
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests
import asyncio
import aiohttp
import zipfile
import shutil


def upload_files_to_mineru(token: str, files: List[Path], model_version: str = "vlm") -> Optional[str]:
    """
    上传文件到 MinerU 批量接口

    参数:
        token: MinerU API token
        files: 需要上传的文件路径列表
        model_version: 模型版本，默认 "vlm"

    返回:
        str: batch_id 或 None（失败时）
    """
    url = "https://mineru.net/api/v4/file-urls/batch"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {
        "files": [{"name": f.name, "data_id": f.stem} for f in files],
        "model_version": model_version
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Upload request failed: status={response.status_code}")
        return None

    result = response.json()
    if result["code"] != 0:
        print(f"Apply upload url failed: {result.get('msg')}")
        return None

    batch_id = result["data"]["batch_id"]
    urls = result["data"]["file_urls"]

    for file_path, upload_url in zip(files, urls):
        with open(file_path, "rb") as f:
            res = requests.put(upload_url, data=f)
        status = "OK" if res.status_code == 200 else f"FAIL code={res.status_code}"
        print(f"[{status}] {file_path.name}")

    return batch_id


async def _download_file(session: aiohttp.ClientSession, url: str, save_path: Path) -> bool:
    """
    异步下载单个文件

    参数:
        session: aiohttp会话
        url: 下载URL
        save_path: 保存路径

    返回:
        bool: 是否成功
    """
    async with session.get(url) as resp:
        if resp.status != 200:
            print(f"Download failed: {url} code={resp.status}")
            return False
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(await resp.read())
        print(f"[OK] {save_path.name}")
        return True


async def query_and_download_all_results_async(
    token: str,
    batch_id: str,
    output_dir: Path,
    poll_interval: float = 2.0
) -> Optional[List[Dict[str, Any]]]:
    """
    轮询 MinerU 批量转换状态，全部完成后异步下载所有 ZIP

    参数:
        token: API token
        batch_id: 上传返回的 batch_id
        output_dir: ZIP 下载目录
        poll_interval: 轮询间隔（秒）

    返回:
        List[Dict[str, Any]]: extract_result 列表 或 None
    """
    url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    headers = {"Authorization": f"Bearer {token}"}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            async with session.get(url) as res:
                if res.status != 200:
                    print(f"HTTP {res.status}: {await res.text()}")
                    return None

                data = await res.json()
                extract_results = data["data"]["extract_result"]

                done = sum(1 for item in extract_results if item["state"] == "done")
                total = len(extract_results)
                print(f"\rProgress: {done}/{total}", end="", flush=True)

                if all(item["state"] == "done" for item in extract_results):
                    print("\nAll done. Downloading...")
                    break

            await asyncio.sleep(poll_interval)

        tasks = []
        for item in extract_results:
            if item.get("full_zip_url"):
                save_path = output_dir / f"{item['data_id']}.zip"
                tasks.append(_download_file(session, item["full_zip_url"], save_path))

        await asyncio.gather(*tasks)
        return extract_results


def extract_md_from_folders(
    zip_paths: List[Path],
    output_dir: Optional[Path] = None,
    delete_zip: bool = False
) -> List[Path]:
    """
    解压 ZIP 列表，从每个 ZIP 解压出的文件夹中提取唯一的 .md 文件

    参数:
        zip_paths: ZIP 文件路径列表
        output_dir: 统一输出目录（None 则输出到 ZIP 同目录下）
        delete_zip: 解压后是否删除 ZIP

    返回:
        List[Path]: 成功提取的 MD 文件路径列表
    """
    extracted: List[Path] = []

    for zip_path in zip_paths:
        zip_path = Path(zip_path)
        if not zip_path.is_file() or zip_path.suffix.lower() != ".zip":
            print(f"[SKIP] {zip_path.name} is not a valid zip")
            continue

        out_dir = zip_path.with_suffix("")
        if out_dir.exists():
            print(f"[SKIP] Directory already exists: {out_dir.name}")
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(out_dir)
                print(f"[OK] Extracted: {zip_path.name}")
            except zipfile.BadZipFile:
                print(f"[ERROR] Bad zip: {zip_path.name}")
                continue

        md_files = list(out_dir.glob("*.md"))
        if not md_files:
            print(f"[WARN] No .md found in {out_dir.name}")
            continue
        if len(md_files) > 1:
            print(f"[WARN] Multiple .md in {out_dir.name}: {[f.name for f in md_files]}")

        md_file = md_files[0]
        target_dir = Path(output_dir) if output_dir else zip_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        new_path = target_dir / (out_dir.name + ".md")

        shutil.move(str(md_file), str(new_path))
        print(f"[OK] Moved to: {new_path.name}")
        extracted.append(new_path)

        # 删除解压后的文件夹，保留 zip 原文件
        shutil.rmtree(out_dir)

        if delete_zip:
            zip_path.unlink()

    print(f"\nTotal extracted: {len(extracted)} MD files")
    return extracted