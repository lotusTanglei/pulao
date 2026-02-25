
import json
import os
from pathlib import Path
from typing import List, Dict
from src.logger import logger
from src.config import CONFIG_DIR

HISTORY_FILE = CONFIG_DIR / "history.json"

class MemoryManager:
    """Manages persistent conversation history."""
    
    @staticmethod
    def load_history() -> List[Dict]:
        """Load conversation history from JSON file."""
        if not HISTORY_FILE.exists():
            return []
            
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                if isinstance(history, list):
                    return history
                else:
                    logger.warning("History file corrupted (not a list), resetting.")
                    return []
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return []

    @staticmethod
    def save_history(history: List[Dict]):
        """Save conversation history to JSON file."""
        try:
            # Simple optimization: Keep last 50 messages to avoid infinite growth
            # But keep the first one if it's system prompt?
            # Actually AISession manages system prompt separately.
            # Let's just save whatever is passed, but maybe limit size.
            
            # Ensure directory exists
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    @staticmethod
    def clear_history():
        """Clear conversation history."""
        if HISTORY_FILE.exists():
            try:
                os.remove(HISTORY_FILE)
            except Exception as e:
                logger.error(f"Failed to clear history: {e}")
