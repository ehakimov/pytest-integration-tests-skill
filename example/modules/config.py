"""Environment settings (config.yml) and secrets (environment variables, locally from .env)."""
import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")  # variables already set (CI) are not overridden


def get_env(name: str) -> str:
    """Required environment variable: a clear error instead of None."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set (see .env.example)")
    return value


@lru_cache
def load_config(env: str) -> dict:
    with open(ROOT_DIR / "config.yml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if env not in config:
        raise RuntimeError(f"Environment {env!r} is not in config.yml. Available: {', '.join(config)}")
    return config[env]
