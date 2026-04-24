import yaml
from pathlib import Path

_CFG_CACHE = None

def get_cfg(cfg_path: Path = None) -> dict:
    global _CFG_CACHE
    if _CFG_CACHE is not None:
        return _CFG_CACHE

    if cfg_path is None:
        cfg_path = Path(__file__).parent.parent / "config" / "config.yaml"

    with open(cfg_path, "r", encoding="utf-8") as f:
        _CFG_CACHE = yaml.safe_load(f)

    return _CFG_CACHE