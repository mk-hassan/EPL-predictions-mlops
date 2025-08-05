"""
Configuration package for EPL predictions.

This package provides centralized access to all configuration files
and settings used throughout the EPL predictions pipeline.

Usage:
    from config import params

    # Access required columns
    cols = params.required_columns
"""

import yaml
from pathlib import Path
import logging

from .config import get_config

# Package metadata
__version__ = "1.0.0"
__author__ = "EPL Predictions Team"

# Setup logging
logger = logging.getLogger(__name__)

# Get the config directory path
CONFIG_DIR = Path(__file__).parent


class ConfigLoader:
    """Utility class for loading YAML configuration files."""

    @staticmethod
    def load_yaml(file_path: Path) -> dict[str, any]:
        """Load a YAML file and return its contents."""
        try:
            with open(file_path, encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {file_path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading {file_path}: {e}")
            return {}


class ConfigObject:
    """Base class for configuration objects with dot notation access."""

    def __init__(self, data: dict[str, any]):
        """Initialize config object with dictionary data."""
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, ConfigObject(value))
            elif isinstance(value, list):
                setattr(self, key, value)
            else:
                setattr(self, key, value)

    def __getattr__(self, name: str) -> any:
        """Allow dot notation access to configuration values."""
        raise AttributeError(f"Configuration key '{name}' not found")

    def get(self, key: str, default: any = None) -> any:
        """Get configuration value with default fallback."""
        return getattr(self, key, default)


# Load configuration files - YAML only
def _load_params() -> ConfigObject:
    """Load required columns configuration."""
    yaml_path = CONFIG_DIR / "params.yaml"

    if yaml_path.exists():
        data = ConfigLoader.load_yaml(yaml_path)
        logger.info("Loaded required_columns from YAML")
    else:
        logger.warning("No params.yaml file found")
        data = {"required_columns": [], "ml_features": {}}

    return ConfigObject(data)


# Load all configurations on import
try:
    params = _load_params()
    logger.info("All configuration files loaded successfully")
except Exception as e:
    logger.error(f"Error loading configurations: {e}")
    params = ConfigObject({})


# Convenience functions
def get_required_columns() -> list:
    """Get list of required columns."""
    return getattr(params, 'required_columns', [])


def get_ml_features() -> dict[str, any]:
    """Get ML features configuration."""
    return getattr(params, 'ml_features', {})


# Public API
__all__ = ["params", "get_required_columns", "get_ml_features", "ConfigObject", "get_config"]

logger.info("Config package initialized - YAML only")
