# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

磁热材料文献信息提取工具，将论文 PDF 通过 MinerU 转 MD，LLM 提取为 JSON，最终合并为 CSV。

## 工作流程

```
paper/*.pdf → MinerU API → md_zip/*.zip → 解压 → md/*.md → LLM(JSON) → json/*.json → json2csv.py → result.csv
```

## 常用命令

```bash
# PDF → MD（MinerU批量转换）
uv run python scripts/pdf2md.py

# MD → JSON（LLM提取）
uv run python scripts/md2json.py

# JSON → CSV（合并输出）
uv run python scripts/json2csv.py
```

## 架构说明

**三层结构**：
- `scripts/`：入口脚本，串联流程，不可包含业务逻辑
- `src/`：核心功能模块
  - `mineru_client.py`：MinerU API 调用（上传、轮询、下载、解压）
  - `llm_extractor.py`：`BatchExtractor` 异步批量提取器，基于 LangChain structured output
  - `models.py`：Pydantic 数据模型（`MagnetocaloricData` / `MagnetocaloricDataList`）
- `utils/config.py`：YAML 配置加载（单例缓存）

**配置管理**：所有 API 密钥和模型参数通过 `config/config.yaml` 管理，`utils.config.get_cfg()` 读取。

**LLM 提取逻辑**：原文过滤移除参考文献/致谢/Supplementary章节；使用 `temperature=0.1` 减少幻觉；`max_concurrent=10` 控制并发。

## 数据模型

6个必填字段：`alloy_composition`（合金成分）、`sample_preparation`（制备方法）、`max_magnetic_entropy`（最大磁熵变）、`temperature`（对应温度）、`magnetic_field`（外加磁场）、`source_pdf`（来源文件）。