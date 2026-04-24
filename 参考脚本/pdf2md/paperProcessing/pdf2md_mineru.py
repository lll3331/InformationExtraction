from typing import List, Dict, Any, Optional
from pathlib import Path
import requests
import shutil


def upload_files_to_mineru(token: str, files: List[Path], model_version: str = "vlm"):
    """
    上传文件到 Mineru，将本地文件上传到批量上传接口。

    参数:
        token: Mineru 官网申请的 API token
        files: List[Path], 需要上传的文件路径列表
        model_version: Mineru VLM 模型版本

    返回:
        dict, API 返回结果
    """
    url = "https://mineru.net/api/v4/file-urls/batch"
    header = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # 构造 API 输入
    data = {
        "files": [{"name": f.name, "data_id": f.stem} for f in files],
        "model_version": model_version
    }

    try:
        response = requests.post(url, headers=header, json=data)
        if response.status_code != 200:
            print(f"response not success. status:{response.status_code} ,result:{response.text}")
            return None

        result = response.json()
        # print("response success:", result)

        if result["code"] != 0:
            print("apply upload url failed:", result.get("msg"))
            return None

        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]

        # print(f"batch_id: {batch_id}")
        # print(f"upload urls: {urls}")

        # 执行上传
        for file_path, upload_url in zip(files, urls):
            with open(file_path, "rb") as f:
                res_upload = requests.put(upload_url, data=f)
                if res_upload.status_code == 200:
                    print(f"{file_path.name} upload success")
                else:
                    print(f"{file_path.name} upload failed, code={res_upload.status_code}")

        return batch_id

    except Exception as err:
        print("Error:", err)
        return None

import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Any, Optional, List

async def download_file_async(session, url: str, save_path: Path):
    """异步下载文件"""
    async with session.get(url) as resp:
        if resp.status != 200:
            print(f"Download failed: {url} code={resp.status}")
            return False

        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(await resp.read())

        print(f"Saved {save_path}")
        return True

async def query_and_download_all_results_async(
    token: str,
    batch_id: str,
    output_dir: Path,
    poll_interval: float = 1.0
) -> Optional[List[Dict[str, Any]]]:
    """
    异步查询 Mineru 多文件状态，等待所有文件都 done，并下载每个 full_zip_url。

    参数:
        token: API token
        batch_id: 上传后返回的 batch_id
        output_dir: 下载 ZIP 的保存目录
        poll_interval: 轮询时间（秒）

    返回：
        List[dict] extract_result 全部条目
    """

    url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"Checking extract result for batch_id: {batch_id}")

    async with aiohttp.ClientSession(headers=headers) as session:
        last_states = {}

        while True:
            async with session.get(url) as res:
                if res.status != 200:
                    print(f"HTTP {res.status} error: {await res.text()}")
                    return None

                data = await res.json()
                extract_results = data["data"]["extract_result"]

                # 打印所有文件的当前状态
                # msg = " | ".join([f"{item['file_name']}:{item['state']}" for item in extract_results])
                # print(f"\r{msg}", end="", flush=True)
                done_count = sum(1 for item in extract_results if item["state"] == "done")
                total_count = len(extract_results)
                print(f"\rProgress: {done_count}/{total_count}", end="", flush=True)

                # 判断是否全部完成
                all_done = all(item["state"] == "done" for item in extract_results)

                if all_done:
                    print("\nAll files done. start downloading...")
                    break

            await asyncio.sleep(poll_interval)

        # -------------------------------
        #    下载所有 full_zip_url
        # -------------------------------
        tasks = []
        for item in extract_results:
            if item["state"] == "done" and item.get("full_zip_url"):
                save_path = output_dir / f"{item['data_id']}.zip"
                tasks.append(download_file_async(session, item["full_zip_url"], save_path))

        await asyncio.gather(*tasks)

        return extract_results


import zipfile
def extract_zip_list(zip_paths, overwrite=False, remove_zip=False):
    """
    解压一组 ZIP 文件到各自所在的文件夹中。

    参数：
        zip_paths (List[Path]): ZIP 文件路径列表
        overwrite (bool): 若目标文件夹存在，是否覆盖
        remove_zip (bool): 解压成功后是否删除 ZIP 原文件

    返回：
        List[Path]: 解压后的文件夹路径列表
    """
    extracted_dirs = []

    for zip_path in zip_paths:
        zip_path = Path(zip_path)

        # 检查文件是否存在
        if not zip_path.is_file():
            print(f"[跳过] 文件不存在: {zip_path}")
            continue

        # 检查是否为 zip
        if zip_path.suffix.lower() != ".zip":
            print(f"[跳过] 不是 ZIP 文件: {zip_path}")
            continue

        # 目标解压文件夹（与 zip 同名）
        out_dir = zip_path.with_suffix("")

        # 处理已存在文件夹
        if out_dir.exists():
            if not overwrite:
                print(f"[跳过] 目标文件夹已存在: {out_dir}")
                extracted_dirs.append(out_dir)
                continue
        else:
            out_dir.mkdir(parents=True, exist_ok=True)

        # 解压
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(out_dir)
            print(f"[完成] 解压: {zip_path.name} -> {out_dir}")
            extracted_dirs.append(out_dir)

            # 删除 ZIP 文件
            if remove_zip:
                try:
                    zip_path.unlink()
                    print(f"[已删除 ZIP] {zip_path}")
                except Exception as e:
                    print(f"[删除失败] {zip_path}: {e}")

        except zipfile.BadZipFile:
            print(f"[错误] 非法或损坏的 ZIP 文件: {zip_path}")

    return extracted_dirs


def extract_md_from_folders(
    input_dirs: List[Path],
    output_dir: Path = None,
    delete_input: bool = False
) -> List[Path]:
    """
    从多个 MinerU 转换后的文件夹中提取 MD 文件

    Args:
        input_dirs: 多个输入目录路径
        output_dir: 统一输出目录（若为 None，则各自使用 parent 目录）
        delete_input: 是否删除输入目录

    Returns:
        List[Path]: 所有成功提取的 MD 文件路径列表
    """

    print("~" * 36)
    print("开始批量提取 MD 文件...")

    extracted_files = []

    for input_dir in input_dirs:
        print("\n" + "-" * 30)
        print(f"处理目录: {input_dir}")

        # 检查目录
        if not input_dir.exists() or not input_dir.is_dir():
            print(f"❌ 错误: 输入目录不存在或不是目录: {input_dir}")
            continue

        # 查找 MD 文件
        md_files = list(input_dir.glob("*.md"))
        if len(md_files) == 0:
            print(f"❌ 未找到 MD 文件")
            continue
        elif len(md_files) > 1:
            print(f"❌ 找到多个 MD 文件: {[f.name for f in md_files]}")
            continue

        md_file = md_files[0]
        print(f"✔ 找到 MD 文件: {md_file.name}")

        # 决定输出目录
        if output_dir is None:
            odir = input_dir.parent
            print(f"使用默认输出目录: {odir}")
        else:
            odir = Path(output_dir)
            odir.mkdir(parents=True, exist_ok=True)

        # 输出文件名 = 原目录名.md
        new_filename = input_dir.name + ".md"
        output_file = odir / new_filename

        try:
            shutil.move(str(md_file), str(output_file))
            print(f"✔ 提取到: {output_file}")

            if delete_input:
                shutil.rmtree(input_dir)
                print(f"🗑 已删除目录: {input_dir}")

            extracted_files.append(output_file)

        except Exception as e:
            print(f"❌ 处理时出错: {e}")

    print("\n全部完成！成功提取:", len(extracted_files), "个文件")
    return extracted_files
