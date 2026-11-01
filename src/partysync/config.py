"""Persistent settings and speaker-pair presets."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def config_path() -> Path:
    """Return the JSON settings path."""
    return Path.home() / ".partysync" / "config.json"

def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load settings, returning defaults for missing or corrupt files."""
    try:
        return json.loads((path or config_path()).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"pairs": {}}

def save_config(data: dict[str, Any], path: Path | None = None) -> None:
    """Atomically persist JSON settings."""
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")

def pair_key(a: str, b: str) -> str:
    """Return an order-independent speaker-pair key."""
    return "|".join(sorted((a, b), key=str.casefold))
