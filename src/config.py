import os
import yaml
from pathlib import Path
from typing import Optional, Dict
from src.i18n import set_language

# Use a safe config directory, fallback to temp if home is not writable
try:
    CONFIG_DIR = Path.home() / ".pulao"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    import tempfile
    CONFIG_DIR = Path(tempfile.gettempdir()) / "pulao"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "config.yaml"
GLOBAL_CONFIG_FILE = Path("/opt/pulao/global_config.yaml")

DEFAULT_CONFIG = {
    "current_provider": "default",
    "providers": {
        "default": {
            "api_key": "",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-reasoner",
        }
    },
    "language": "en"
}

def load_config() -> Dict:
    """Load configuration from file or return defaults."""
    # Start with defaults
    final_config = DEFAULT_CONFIG.copy()
    
    # Helper to migrate old flat config to new nested structure
    def migrate_flat_config(cfg):
        if "api_key" in cfg and "providers" not in cfg:
            return {
                "current_provider": "default",
                "providers": {
                    "default": {
                        "api_key": cfg.get("api_key", ""),
                        "base_url": cfg.get("base_url", ""),
                        "model": cfg.get("model", "")
                    }
                },
                "language": cfg.get("language", "en")
            }
        return cfg

    # 1. Load Global Config
    if GLOBAL_CONFIG_FILE.exists():
        try:
            with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                global_config = yaml.safe_load(f) or {}
                # Handle migration if global config is old format
                global_config = migrate_flat_config(global_config)
                # Deep update is tricky, for now just top level update
                # Ideally we should merge providers dict
                if "providers" in global_config:
                    final_config["providers"].update(global_config["providers"])
                final_config.update({k: v for k, v in global_config.items() if k != "providers"})
        except Exception:
            pass

    # 2. Load User Config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
                user_config = migrate_flat_config(user_config)
                
                if "providers" in user_config:
                    # Ensure providers dict exists in final_config
                    if "providers" not in final_config:
                        final_config["providers"] = {}
                    final_config["providers"].update(user_config["providers"])
                
                final_config.update({k: v for k, v in user_config.items() if k != "providers"})
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
    
    # Backward compatibility: flatten current provider into root for legacy code access
    current_provider_name = final_config.get("current_provider", "default")
    provider_config = final_config.get("providers", {}).get(current_provider_name, {})
    
    final_config["api_key"] = provider_config.get("api_key", "")
    final_config["base_url"] = provider_config.get("base_url", "")
    final_config["model"] = provider_config.get("model", "")

    # Set language immediately after loading
    set_language(final_config.get("language", "en"))
            
    return final_config

def save_config(config_data: Dict):
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Remove flattened keys before saving to keep structure clean
    to_save = config_data.copy()
    to_save.pop("api_key", None)
    to_save.pop("base_url", None)
    to_save.pop("model", None)
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(to_save, f)
    
    # Update current runtime language
    set_language(to_save.get("language", "en"))
    
    return CONFIG_FILE

def add_provider(name: str, api_key: str, base_url: str, model: str):
    """Add or update a provider."""
    cfg = load_config()
    if "providers" not in cfg:
        cfg["providers"] = {}
    
    cfg["providers"][name] = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model
    }
    # If this is the first custom provider (and default is empty), switch to it
    if name != "default" and cfg["providers"].get("default", {}).get("api_key") == "":
        cfg["current_provider"] = name
        
    save_config(cfg)
    return CONFIG_FILE

def switch_provider(name: str):
    """Switch current provider."""
    cfg = load_config()
    if name not in cfg.get("providers", {}):
        raise ValueError(f"Provider '{name}' not found.")
    
    cfg["current_provider"] = name
    save_config(cfg)
    return CONFIG_FILE