"""
iMessage integration module.
Currently uses MOCK implementations for testing integration.
"""
import time
import json
import builtins
from pathlib import Path

# Path to config
CONFIG_PATH = Path(__file__).parent.parent / "data" / "imessage_config.json"

def load_config() -> dict:
    """Load iMessage config from JSON file."""
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text())

def send_message(recipient: str, message: str) -> bool:
    """
    Mock send message.
    Prints the message to console and sleeps.
    """
    print(f"\n[MOCK SEND] To: {recipient}")
    print(f"[MOCK SEND] Message: {message}")
    time.sleep(1)
    return True

def wait_for_reply(recipient: str, timeout_seconds: int = 120) -> str | None:
    """
    Mock wait for reply.
    Asks user for input via console.
    """
    print(f"\n[MOCK WAIT] Waiting for reply from {recipient}...")
    time.sleep(1)
    try:
        reply = input(f"[MOCK INPUT] Enter reply from {recipient}: ")
        return reply.strip()
    except EOFError:
        return None
