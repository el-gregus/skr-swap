"""Configuration loader with environment variable support."""
import os
import re
from typing import Any, Dict
from pathlib import Path
import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in config values."""
    if isinstance(value, str):
        # Replace ${VAR_NAME} with environment variable value
        pattern = r'\$\{([^}]+)\}'
        matches = re.findall(pattern, value)
        for var_name in matches:
            env_value = os.getenv(var_name, '')
            value = value.replace(f'${{{var_name}}}', env_value)
        return value
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file with environment variable expansion.

    Args:
        config_path: Path to config.yaml file

    Returns:
        Configuration dictionary
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r') as f:
        config = yaml.safe_load(f)

    # Expand environment variables
    config = _expand_env_vars(config)

    # Apply environment variable overrides
    if log_level := os.getenv("LOG_LEVEL"):
        config.setdefault("logging", {})["level"] = log_level

    if rpc_url := os.getenv("SOLANA_RPC_URL"):
        config.setdefault("solana", {})["rpc_url"] = rpc_url

    if jupiter_url := os.getenv("JUPITER_API_URL"):
        config.setdefault("jupiter", {})["api_url"] = jupiter_url

    return config
