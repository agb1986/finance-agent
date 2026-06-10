"""Load role definitions and model assignments from config/roles.yaml."""

from pathlib import Path

import yaml
from common.logger import get_logger

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "roles.yaml"

REQUIRED_KEYS = {"models", "max_tokens", "panel", "debate", "judge"}


def load_config(path: Path = CONFIG_PATH) -> dict:
    """
    Load and validate the roles config.

    Args:
        path: Path to the YAML config. Defaults to the skill's config/roles.yaml.

    Returns:
        The parsed config dict with keys: models, max_tokens, panel, debate, judge.

    Raises:
        ValueError: If any required top-level key is missing.
    """
    logger = get_logger()
    logger.debug(f"loading roles config from {path}")

    config = yaml.safe_load(path.read_text())
    missing = REQUIRED_KEYS - set(config)
    if missing:
        raise ValueError(f"roles config missing keys: {sorted(missing)}")

    logger.debug(f"config loaded: {len(config['panel'])} panel roles")
    return config
