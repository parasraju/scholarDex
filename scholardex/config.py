"""Configuration handling for scholarDex.

Reads/writes a config file at ~/.scholardex/config.toml.
Stores only what users genuinely configure: the Gemini API key and
model name. Everything else is code, not config.
"""

from __future__ import annotations

import os
from pathlib import Path

import toml

from .errors import ConfigError

CONFIG_DIR = Path.home() / ".scholardex"
CONFIG_PATH = CONFIG_DIR / "config.toml"
DEFAULT_MODEL = "gemini-2.5-flash"

_DEFAULT_CONFIG = {"gemini": {"api_key": "", "model": DEFAULT_MODEL}}


def load_config() -> dict:
    """Load config, creating defaults if missing."""
    if not CONFIG_PATH.exists():
        save_config(_DEFAULT_CONFIG)
    return toml.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(toml.dumps(config), encoding="utf-8")


def api_key() -> str:
    """Return the configured API key (config file or GEMINI_API_KEY env)."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        key = load_config().get("gemini", {}).get("api_key", "")
    if not key:
        raise ConfigError(
            "No Gemini API key found. Run `scholardex config --set-key KEY`, "
            "or set the GEMINI_API_KEY environment variable."
        )
    return key


def model() -> str:
    """Return the configured model name."""
    return load_config().get("gemini", {}).get("model", DEFAULT_MODEL)
