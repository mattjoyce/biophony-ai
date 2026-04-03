"""Shared config loader for biophony-ai using loaden."""

from pathlib import Path

from loaden import load_config as _loaden_load


_PATH_SUFFIXES = ("_path", "_directory")


def _expand_paths(config: dict) -> None:
    """Expand top-level keys ending in _path or _directory in-place."""
    for key, value in config.items():
        if isinstance(value, str) and key.endswith(_PATH_SUFFIXES):
            config[key] = str(Path(value).expanduser().resolve())


def load_config(config_path: str) -> dict:
    """Load YAML config via loaden with path expansion."""
    config = _loaden_load(config_path)
    _expand_paths(config)
    return config
