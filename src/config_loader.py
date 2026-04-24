"""分层配置加载器：支持 default.yaml + custom.yaml 合并和环境变量展开"""
import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigLoader:
    """分层配置加载器"""

    _instance: Optional['ConfigLoader'] = None

    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}
        self._loaded: bool = False
        self._custom_path: Optional[Path] = None

    @classmethod
    def get_instance(cls) -> 'ConfigLoader':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置实例，用于测试或切换配置"""
        if cls._instance is not None:
            cls._instance._loaded = False
            cls._instance._config = {}
            cls._instance._custom_path = None

    def load(self, custom_path: Optional[Path] = None, config_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        加载分层配置

        参数:
            custom_path: 自定义配置文件的路径（相对于项目根目录）
            config_dir: 配置目录路径，默认为项目根目录的 config 文件夹

        返回:
            Dict[str, Any]: 合并后的配置字典
        """
        if self._loaded and self._custom_path == custom_path:
            return self._config

        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "config"

        self._custom_path = custom_path

        # 1. 加载 default.yaml
        default_path = config_dir / "default.yaml"
        if default_path.exists():
            with open(default_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {}

        # 2. 加载 custom yaml（覆盖 default）
        if custom_path is not None:
            custom_path = Path(custom_path)
            if not custom_path.is_absolute():
                project_root = Path(__file__).parent.parent
                custom_path = project_root / custom_path

            if custom_path.exists():
                with open(custom_path, "r", encoding="utf-8") as f:
                    custom = yaml.safe_load(f) or {}
                self._config = self._deep_merge(self._config, custom)

        # 3. 展开环境变量
        self._config = self._expand_env_vars(self._config)

        self._loaded = True
        return self._config

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        深度合并字典

        参数:
            base: 基础字典
            override: 覆盖字典

        返回:
            Dict[str, Any]: 合并后的字典
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            elif value is None:
                # None 值不覆盖
                continue
            else:
                result[key] = value
        return result

    def _expand_env_vars(self, obj: Any) -> Any:
        """
        递归展开 ${VAR} 形式的环境变量

        参数:
            obj: 要展开的对象

        返回:
            Any: 展开后的对象
        """
        if isinstance(obj, str):
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, obj)
            for var_name in matches:
                obj = obj.replace(f"${{{var_name}}}", os.environ.get(var_name, ""))
            return obj
        elif isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        return obj

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        点号路径获取配置值

        参数:
            key_path: 点号分隔的路径，如 "llm.temperature"
            default: 默认值

        返回:
            Any: 配置值
        """
        keys = key_path.split(".")
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置字典"""
        return self._config


def get_cfg(custom_path: Optional[Path] = None) -> ConfigLoader:
    """
    便捷函数：获取配置加载器实例

    参数:
        custom_path: 自定义配置文件路径

    返回:
        ConfigLoader: 配置加载器实例
    """
    loader = ConfigLoader.get_instance()
    if not loader._loaded:
        loader.load(custom_path)
    return loader