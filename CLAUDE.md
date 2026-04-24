# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

泛用性 PDF→结构化JSON→CSV 框架，通过 MinerU 将 PDF 转为 Markdown，LLM 提取为结构化 JSON，最终合并为 CSV。

可通过定义不同的 Schema 和 Prompt 模板，提取任意类型的结构化数据。

## 工作流程

```
paper/{子文件夹}/*.pdf → MinerU → md_zip/{子文件夹}/*.zip → 解压 → md/{子文件夹}/*.md
→ LLM(JSON) → json/{子文件夹}/*.json → json2csv.py → results/{子文件夹}.csv
```

## 常用命令

所有参数通过脚本开头设置，无需命令行传参：

```bash
uv run python scripts/pdf2md.py   # 修改脚本开头 SUB_FOLDER 选择子文件夹
uv run python scripts/md2json.py
uv run python scripts/json2csv.py
```

## 配置系统

**分层配置**：`脚本强制设置 > 脚本变量 > CONFIG_FILE 对应 yaml > default.yaml`

每个脚本开头有统一参数区：
```python
# ---------- YAML 配置路径 ----------
CONFIG_FILE = "config/custom_magnetocaloric.yaml"

# ---------- 运行时强制设置 ----------
SUB_FOLDER = "NiMnIn"    # 必须设置：处理哪个子文件夹，None 表示处理所有

# ---------- 运行时覆盖（默认 None，覆盖时生效） ----------
PAPER_DIR = None
MD_DIR = None
JSON_DIR = None
SCHEMA_FILE = None
PROMPT_FILE = None
TEMPERATURE = None
# ...
```

## 子文件夹支持

脚本支持按子文件夹组织数据：
- `paper/NiMnSn/`、`paper/NiMnIn/` 等子文件夹
- 输出到对应的 `md/NiMnSn/`、`json/NiMnSn/` 等子文件夹
- `results/NiMnSn.csv`、`results/NiMnIn.csv` 等最终 CSV

修改 `SUB_FOLDER` 变量选择要处理的子文件夹。

## 目录结构

```
config/
├── default.yaml               # 框架默认配置
├── custom_magnetocaloric.yaml # 磁热材料任务配置
├── custom_battery.yaml        # 电池研究任务配置（示例）
├── schemas/                   # Schema 定义
│   └── magnetocaloric.json
└── prompts/                   # Prompt 模板
    └── magnetocaloric.md

src/
├── config_loader.py           # 分层配置加载器（支持 ${VAR} 环境变量展开）
├── pydantic_generator.py      # JSON Schema → Pydantic 模型
├── llm_extractor.py           # 异步批量提取器
├── mineru_client.py           # MinerU API 调用
└── config.py                  # 旧版配置加载（兼容）

scripts/
├── pdf2md.py                  # PDF → MD
├── md2json.py                 # MD → JSON
└── json2csv.py                # JSON → CSV

paper/                         # PDF 源文件（按子文件夹组织）
├── NiMnSn/
└── NiMnIn/

results/                       # 最终 CSV 输出
├── NiMnSn.csv
└── NiMnIn.csv
```

## Schema 格式

`config/schemas/magnetocaloric.json`：
```json
{
  "name": "magnetocaloric",
  "description": "磁热材料文献信息提取",
  "fields": [
    {"name": "alloy_composition", "type": "string", "description": "合金化学成分", "example": "Ni50Mn35Sn15"},
    {"name": "sample_preparation", "type": "string", "description": "样品制备方法", "example": "感应熔炼+退火+淬火"}
  ]
}
```

## 环境变量

配置文件中支持 `${VAR}` 形式的环境变量展开。常用环境变量：
- `MINERU_API_TOKEN`：MinerU API 密钥
- `LLM_API_KEY`：LLM API 密钥

在 Windows 上运行前需先设置：
```cmd
set MINERU_API_TOKEN=你的token
set LLM_API_KEY=你的key
```