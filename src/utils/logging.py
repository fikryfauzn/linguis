import logging
import os
from pathlib import Path
from typing import Optional

# Constants defined in Spec 9.2.1
LOG_DIR = Path(os.path.expanduser("~/.local/share/reader-app/logs"))
LOG_FILE = LOG_DIR / "app.log"

def setup_logging() -> None:
    """
    Initializes the logging system.
    Creates the directory structure if it doesn't exist.
    Configures the root logger to write to file.
    """
    # Ensure log directory exists
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"CRITICAL: Failed to create log directory: {e}")
        return

    # Spec 9.2.2 Configuration
    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.INFO,  # Default to INFO as per spec
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        filemode='a'  # Append mode
    )
    
    # log immediate startup event
    logging.getLogger("System").info(f"Logging initialized at {LOG_FILE}")

def get_logger(name: str) -> logging.Logger:
    """Returns a named logger instance."""
    return logging.getLogger(name)

def sanitize_for_log(text: str, max_len: int = 20) -> str:
    """
    Spec 11.5.2: Sanitize text for logging.
    Redacts actual content to protect user privacy.
    """
    if text is None:
        return "[NONE]"
        
    if len(text) <= max_len:
        return "[REDACTED]"
    
    return f"[REDACTED: {len(text)} chars]"