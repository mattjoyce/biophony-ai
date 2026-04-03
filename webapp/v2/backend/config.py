#!/usr/bin/env python3
"""
Configuration management for AudioMoth Spectrogram Viewer
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Reach repo root so config_utils is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config_utils import load_config as _load_config_base


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        return _load_config_base(config_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}")


def setup_cli() -> argparse.Namespace:
    """Setup command line interface"""
    parser = argparse.ArgumentParser(description='AudioMoth Spectrogram Viewer')
    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path (default: config.yaml)'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=8001,
        help='Port to run the server on (default: 8001)'
    )
    
    return parser.parse_args()