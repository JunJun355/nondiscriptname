"""Configuration constants for PollEV automation."""
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SESSION_STATE_DIR = DATA_DIR / "session_state"
CLASSES_FILE = DATA_DIR / "classes.json"

# URLs
POLLEV_BASE_URL = "https://pollev.com"
POLLEV_LOGIN_URL = "https://pollev.com/login"

# Ensure session directory exists
SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)
