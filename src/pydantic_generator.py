"""JSON Schema → Pydantic 模型动态生成器"""
import json
from pathlib import Path
from typing import Any, Dict, List, Type

from pydantic import BaseModel, Field, create_model


def load_schema(schema_path: Path) -> Dict[str, Any]:
    """
    从 JSON 文件加载 Schema

    参数:
        schema_path: Schema 文件路径

    返回:
        Dict[str, Any]: Schema 字典
    """
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def schema_to_pydantic(schema: Dict[str, Any]) -> Type[BaseModel]:
    """
    将 JSON Schema 转换为 Pydantic 模型类

    参数:
        schema: Schema 字典，应包含 name 和 fields 字段

    返回:
        Type[BaseModel]: 动态生成的 Pydantic 模型类
    """
    model_name = f"{schema['name'].capitalize().replace('_', '')}Data"

    fields_dict: Dict[str, Any] = {}
    for field_def in schema.get("fields", []):
        field_name = field_def["name"]
        field_desc = field_def.get("description", "")
        fields_dict[field_name] = (str, Field(description=field_desc))

    return create_model(model_name, **fields_dict)


def schema_to_list_model(data_model: Type[BaseModel]) -> Type[BaseModel]:
    """
    将数据模型包装为列表模型，以兼容 with_structured_output

    参数:
        data_model: 数据模型类

    返回:
        Type[BaseModel]: 包装后的列表模型类
    """
    list_model_name = data_model.__name__ + "List"

    return create_model(
        list_model_name,
        data=(List[data_model], Field(default_factory=list))
    )


def load_schema_and_generate_models(schema_path: Path) -> tuple:
    """
    加载 Schema 并生成 Pydantic 模型

    参数:
        schema_path: Schema 文件路径

    返回:
        tuple: (data_model, list_model) 元组
    """
    schema = load_schema(schema_path)
    data_model = schema_to_pydantic(schema)
    list_model = schema_to_list_model(data_model)
    return data_model, list_model


def get_schema_field_names(schema_path: Path) -> List[str]:
    """
    从 Schema 文件获取字段名列表（用于 CSV 表头）

    参数:
        schema_path: Schema 文件路径

    返回:
        List[str]: 字段名列表
    """
    schema = load_schema(schema_path)
    return [f["name"] for f in schema.get("fields", [])]