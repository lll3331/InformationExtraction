# 磁热材料文献信息提取工具

PDF → MD → JSON → CSV 批量处理流水线，从论文中自动提取磁热材料关键数据。

## 工作流程

```
paper/*.pdf → MinerU → md_zip/*.zip → 解压 → md/*.md → LLM(JSON) → json/*.json → 合并 → result.csv
```

## 项目结构

```
D:\0AAA\UV\InformationExtraction\
├── config/config.yaml          # API密钥配置
├── paper/                      # PDF源文件（31篇）
├── md_zip/                     # MinerU转换结果（临时）
├── md/                         # 提取的Markdown文件
├── json/                       # LLM结构化JSON输出
├── result.csv                  # 最终数据表格
├── src/
│   ├── mineru_client.py        # MinerU API客户端
│   └── llm_extractor.py        # LLM异步提取器
├── scripts/
│   ├── pdf2md.py               # PDF→MD 入口
│   ├── md2json.py              # MD→JSON 入口
│   └── json2csv.py             # JSON→CSV 入口
└── utils/
    └── config.py               # YAML配置加载
```

## 提取字段

| 字段 | 说明 |
|------|------|
| alloy_composition | 合金化学成分 |
| sample_preparation | 样品制备方法 |
| max_magnetic_entropy | 最大磁熵变（数值+单位） |
| temperature | 对应温度 |
| magnetic_field | 对应磁场 |
| source_pdf | 来源PDF文件名 |

## 使用方法

```bash
# 1. PDF → MD（通过MinerU批量转换）
uv run python scripts/pdf2md.py

# 2. MD → JSON（通过LLM提取结构化数据）
uv run python scripts/md2json.py

# 3. JSON → CSV（合并所有JSON为表格）
uv run python scripts/json2csv.py
```

## 依赖

- aiohttp
- langchain-openai
- pydantic
- pyyaml

## 已验证

- 31篇PDF全部成功转换
- LLM提取31个JSON，100%成功率
- 最终输出43条有效记录到result.csv