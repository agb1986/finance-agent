"""Load and validate the pipeline configuration from pipeline.yaml."""

from pathlib import Path
from typing import Any

import yaml
from common.logger import get_logger

SKILL_ROOT = Path(__file__).parent.parent.parent
DEFAULT_CONFIG_PATH = SKILL_ROOT / "pipeline.yaml"

DEFAULTS: dict[str, Any] = {
    "news": {"hours": 24, "min_semantic": 0.40},
    "tickers": {"top_n": 5},
    "portfolio": {"min_abs_pnl_pct": 5.0, "min_position_value": 25.0, "max_candidates": 3},
    "trader": {"max_runs": 2, "verdict_cache_days": 3, "rounds": 2},
    "email": {"subject_prefix": "Daily Finance Report"},
    "retention_days": 14,
    "pricing": {
        "currency": "$",
        "models": {
            "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
            "claude-opus-4-8": {"input": 5.00, "output": 25.00},
            "claude-opus-5": {"input": 5.00, "output": 25.00},
        },
    },
}


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load pipeline.yaml, overlaying values on top of DEFAULTS.

    Args:
        path: Optional alternative config path. Defaults to the skill-root pipeline.yaml.

    Returns:
        A config dict with every DEFAULTS key present.
    """
    logger = get_logger()
    config_path = path or DEFAULT_CONFIG_PATH

    loaded: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open() as f:
            loaded = yaml.safe_load(f) or {}
        logger.debug(f"loaded config from {config_path}")
    else:
        logger.debug(f"config {config_path} not found — using defaults")

    config: dict[str, Any] = {}
    for key, default in DEFAULTS.items():
        value = loaded.get(key)
        if isinstance(default, dict):
            merged = dict(default)
            if isinstance(value, dict):
                merged.update(value)
            config[key] = merged
        else:
            config[key] = value if value is not None else default
    return config
