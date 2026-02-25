
import logging
import logging.handlers
from pathlib import Path
from src.config import CONFIG_DIR
import sys

# Define log file path
LOG_DIR = CONFIG_DIR
LOG_FILE = LOG_DIR / "pulao.log"

def setup_logging():
    """Configure centralized logging."""
    global LOG_FILE
    
    # Ensure directory exists and is writable
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Fallback to temp dir if home is not writable (e.g. strict sandbox)
        import tempfile
        global LOG_FILE
        LOG_DIR_TEMP = Path(tempfile.gettempdir()) / "pulao"
        LOG_DIR_TEMP.mkdir(parents=True, exist_ok=True)
        LOG_FILE = LOG_DIR_TEMP / "pulao.log"

    logger = logging.getLogger("pulao")
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger

    # File Handler - Rotating (1MB size, keep 5 backups)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1024*1024, backupCount=5, encoding="utf-8"
        )
    except PermissionError:
         # Fallback again if file creation fails
        import tempfile
        LOG_FILE = Path(tempfile.gettempdir()) / "pulao" / "pulao.log"
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1024*1024, backupCount=5, encoding="utf-8"
        )

    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console Handler - WARNING and above only, simple format
    # We want to keep stdout clean for rich console output, so logs mainly go to file
    # unless it's a critical system error that might crash the CLI before rich can handle it.
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.CRITICAL)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create a default logger instance
logger = setup_logging()
