#!/usr/bin/env python3
"""
Configuration management for AudioMoth Spectrogram Viewer
"""

import argparse
import yaml
from typing import Dict, Any


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML configuration: {e}")


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