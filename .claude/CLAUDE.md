## 语言要求

- 所有回答、 Plan、代码中的注释必须使用简体中文，禁止使用英文自然语言，仅允许在代码关键字、库名、类名、函数名中出现英文。

## 虚拟环境

- 使用 uv 管理环境，如需依赖请用 `uv add <package>`。
- **所有 Python 程序必须使用 `uv run <script_name>` 运行**，禁止直接使用 `python` 命令。
  - 原因：直接调用 `python` 会使用系统全局环境，而非项目虚拟环境，可能导致依赖版本冲突或行为不一致。
  - 适用场景：运行脚本、执行模块、调试代码、运行测试等**一切**涉及 Python 的操作。
    - 临时单行命令（如 `python -c "..."`）也应使用 `uv run python -c "..."`，而非直接 `python`
    - 仅当 `uv run` 确实无法满足需求时（如涉及交互式终端、特殊环境变量等），才降级使用 `python`，但仍需确保通过 `uv run --no-project python` 或激活虚拟环境等方式使用项目依赖

- 文件路径统一使用 pathlib. Path，并通过 `from pathlib import Path` 导入。
- 为保证项目迁移后的可重复性，统一使用 **相对路径** ，通过以下方式定位脚本目录与项目根目录，并据此组织路径关系：

  ```python
  from pathlib import Path
  
  current_file = Path(__file__).resolve()
  current_dir = current_file.parent
  project_root = current_file.parents[project_root_level]
  ```

  - 相对于 `current_file` 跨文件夹处理建议使用 `project_root` 处理文件关系
  - 处理 `current_dir` 文件夹及其子文件夹文件时，建议使用 `current_dir` 处理文件关系

## 代码规范

- 所有函数必须包含类型提示和完整中文 docstring，参数类型示例：str、int、float、bool、List[Path]、Dict[str, Any]、Any、Optional[...]、Union[..., ...]。
- 严格遵循 PEP 8 规范，保证代码结构清晰、可读。
- 可配置参数默认放置于脚本开头的常量区域（模块级变量）。

## 代码组织

- **核心代码统一放在 `src` 文件夹下**，可根据功能模块在 `src` 内建立子文件夹组织代码。
- **`scripts` 文件夹仅用于存放调用脚本**，负责将 `src` 中的核心功能串联起来。
- 除非用户明确说明是**临时脚本**或**独立脚本**，否则所有代码都应遵循上述规范，禁止在项目根目录或其他位置直接编写业务逻辑代码。
