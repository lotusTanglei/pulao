import os
import yaml
from pathlib import Path
from typing import Optional, Dict
from src.i18n import set_language

CONFIG_DIR = Path.home() / ".pulao"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
GLOBAL_CONFIG_FILE = Path("/opt/pulao/global_config.yaml")

DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "language": "en"
}

def load_config() -> Dict[str, str]:
    """Load configuration from file or return defaults."""
    final_config = DEFAULT_CONFIG.copy()
    
    # 1. Load Global Config (set by install.sh)
    if GLOBAL_CONFIG_FILE.exists():
        try:
            with open(GLOBAL_CONFIG_FILE, "r") as f:
                global_config = yaml.safe_load(f) or {}
                final_config.update(global_config)
        except Exception:
            pass

    # 2. Load User Config (overrides global)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                user_config = yaml.safe_load(f) or {}
                final_config.update(user_config)
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
    
    # Set language immediately after loading
    set_language(final_config.get("language", "en"))
            
    return final_config

def save_config(api_key: str, base_url: str, model: str, language: str = None):
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing to preserve other fields if any
    current = load_config()
    
    config = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "language": language or current.get("language", "en")
    }
    
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f)
    
    # Update current runtime language
    set_language(config["language"])
    
    return CONFIG_FILE
