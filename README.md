# InformationExtraction

泛用性 PDF → 结构化 JSON → CSV 框架。通过 MinerU 将 PDF 转为 Markdown，LLM 提取为结构化 JSON，最终合并为 CSV。

可通过定义不同的 Schema 和 Prompt 模板，提取任意类型的结构化数据。

## 使用场景

本工具适用于从大量论文/文档中自动提取结构化信息的场景：

- **文献计量分析**：批量提取论文中的材料成分、制备方法、性能参数等
- **知识库构建**：将非结构化文档转为结构化数据
- **数据挖掘**：从专利、标准、报告中提取关键指标
- **多源异构数据整合**：统一不同来源的数据格式

### 示例：磁热材料文献信息提取

| source_md | alloy_composition | sample_preparation | max_magnetic_entropy | temperature | magnetic_field |
|-----------|------------------|-------------------|---------------------|-------------|----------------|
| Chen 等 - 2013 - Magnetic entropy change... | Ni45Co5Mn36.6In13.4 | 感应熔炼+区熔退火+水淬 | 18.5 J/kg·K | 305 K | 5 T |

## 原理

### 整体架构

```
paper/*.pdf → MinerU → md_zip/*.zip → 解压 → md/*.md → LLM(JSON) → json/*.json → 合并 → results/*.csv
```

### 核心组件

| 组件 | 技术 | 作用 |
|------|------|------|
| PDF → MD | MinerU (视觉大模型) | 将 PDF 转为 Markdown，保留公式、表格结构 |
| MD → JSON | LLM (with_structured_output) | 从文本中提取结构化字段 |
| JSON → CSV | Python csv 模块 | 合并多个 JSON 为 CSV |

### 关键技术点

1. **MinerU API**：使用视觉大模型解析 PDF，提取文本、表格、公式
2. **LangChain with_structured_output**：强制 LLM 输出符合 JSON Schema 的结构化数据
3. **异步批量处理**：支持多文件并发处理，提高效率
4. **Windows 中文路径兼容**：通过短路径名（8.3格式）处理含中文字符的路径

## 快速开始

### 环境要求

- Python 3.10+
- uv 包管理器

### 安装依赖

```bash
uv sync
```

### 配置

创建 `config/custom_xxx.yaml`（参考 `config/default.yaml`）：

```yaml
mineru:
  api_token: ${MINERU_API_TOKEN}  # 从环境变量读取

llm:
  api_key: ${LLM_API_KEY}
  base_url: https://api.deepseek.com
  model: qwen3-max

md2json:
  schema_file: config/schemas/xxx.json
  prompt_file: config/prompts/xxx.md
```

### 定义 Schema

`config/schemas/xxx.json`：
```json
{
  "name": "xxx",
  "description": "领域描述",
  "fields": [
    {"name": "field1", "type": "string", "description": "字段说明", "example": "示例值"}
  ]
}
```

### 定义 Prompt 模板

`config/prompts/xxx.md`：
```markdown
你是一个{domain}文献信息提取专家。
请从提供的论文内容中提取以下字段的信息：

{fields_list}

## 输出要求
- 只输出数据，不要有其他解释
- 如果某字段在文中未提及，填 "未提及"

## 字段说明
{field_descriptions}

请以JSON格式输出，包含上述字段。
```

### 运行

```bash
# 1. PDF → MD（通过MinerU批量转换）
uv run scripts/pdf2md.py

# 2. MD → JSON（通过LLM提取结构化数据）
uv run scripts/md2json.py

# 3. JSON → CSV（合并所有JSON为表格）
uv run scripts/json2csv.py

# 4. 预览渲染后的 Prompt（调试用）
uv run scripts/render_prompt.py
```

所有参数通过脚本开头变量设置，无需命令行传参。修改 `SUB_FOLDER` 选择处理的子文件夹。

### 环境变量（Windows）

```cmd
set MINERU_API_TOKEN=你的token
set LLM_API_KEY=你的key
set PYTHONIOENCODING=utf-8
```

## 目录结构

```
├── config/                  # 配置
│   ├── default.yaml         # 默认配置
│   ├── custom_*.yaml       # 任务配置
│   ├── schemas/             # JSON Schema 定义
│   └── prompts/             # Prompt 模板
├── src/                     # 核心代码
│   ├── mineru_client.py     # MinerU API 客户端
│   ├── llm_extractor.py     # LLM 批量提取器
│   ├── config_loader.py     # 分层配置加载器
│   └── pydantic_generator.py # JSON Schema → Pydantic 模型
├── scripts/                 # 入口脚本
│   ├── pdf2md.py            # PDF → MD
│   ├── md2json.py           # MD → JSON
│   ├── json2csv.py          # JSON → CSV
│   └── render_prompt.py     # 渲染 Prompt（调试用）
├── paper/                   # PDF 源文件
│   ├── NiMnIn/              # 按子文件夹组织
│   └── NiMnSn/
├── md/                      # Markdown 输出
├── json/                    # JSON 输出
└── results/                 # 最终 CSV
```

## 扩展自定义任务

1. 在 `config/schemas/` 创建新的 Schema 文件（如 `battery.json`）
2. 在 `config/prompts/` 创建对应的 Prompt 模板（如 `battery.md`）
3. 创建新的 YAML 配置（如 `config/custom_battery.yaml`），指定新的 Schema 和 Prompt 路径
4. 修改脚本开头的 `CONFIG_FILE` 为新配置
5. 修改 `SUB_FOLDER` 为对应的数据子文件夹
6. 运行 `render_prompt.py` 检查渲染结果
7. 依次执行三个脚本

## 依赖

- `aiohttp` - 异步 HTTP 请求
- `langchain-openai` - LLM 接口
- `pydantic` - 数据验证
- `pyyaml` - YAML 配置解析
