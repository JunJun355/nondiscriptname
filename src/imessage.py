#!/usr/bin/env python3
"""
iMessage integration for macOS.

Functions to send and receive iMessages via AppleScript and SQLite.
Includes handling for self-testing via -test flag.
"""
import json
import subprocess
import time
import sys
from pathlib import Path

# Path to config
CONFIG_PATH = Path(__file__).parent.parent / "data" / "imessage_config.json"

# Global test flag
TEST_MODE = "-test" in sys.argv

def load_config() -> dict:
    """Load iMessage config from JSON file."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config not found at {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text())


def send_message(recipient: str, message: str) -> bool:
    """
    Send an iMessage to a recipient (phone number or iCloud email).
    
    Args:
        recipient: Phone number (e.g., "+1234567890") or iCloud email
        message: The message text to send
    
    Returns:
        True if sent successfully, False otherwise
    """
    # Escape quotes and backslashes in message
    escaped_message = message.replace('\\', '\\\\').replace('"', '\\"')
    
    applescript = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetBuddy to participant "{recipient}" of targetService
        send "{escaped_message}" to targetBuddy
    end tell
    '''
    
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"✅ Sent to {recipient}: {message[:50]}...")
            return True
        else:
            print(f"❌ Failed to send: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Timeout sending message")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def get_latest_message(recipient: str) -> tuple[str, int] | None:
    """
    Get the latest message received from a recipient by querying the Messages database.
    Requires Full Disk Access for the terminal running this script.
    
    Args:
        recipient: Phone number or iCloud email address
    
    Returns:
        Tuple of (message_text, rowid) or None if not found.
        The rowid can be used to detect new messages.
    """
    import sqlite3
    import os
    
    # Normalize if it looks like a phone number
    normalized = recipient.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if normalized.startswith("+1"):
        normalized = normalized[2:]
    elif normalized.startswith("1") and len(normalized) == 11:
        normalized = normalized[1:]
    
    db_path = os.path.expanduser("~/Library/Messages/chat.db")
    
    if not os.path.exists(db_path):
        print("❌ Messages database not found")
        return None
    
    try:
        # Connect in read-only mode
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        # Query for messages from this recipient
        # We look for the recipient in the handle table and join to messages
        query = """
        SELECT m.text, m.ROWID, m.is_from_me, m.date
        FROM message m
        JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        JOIN chat c ON cmj.chat_id = c.ROWID
        JOIN chat_handle_join chj ON c.ROWID = chj.chat_id
        JOIN handle h ON chj.handle_id = h.ROWID
        WHERE h.id LIKE ?
        ORDER BY m.date DESC
        LIMIT 10
        """
        
        # Try different formats (normalized and original)
        patterns = [
            f"%{normalized}%",
            f"%{recipient}%",
        ]
        
        for pattern in patterns:
            cursor.execute(query, (pattern,))
            rows = cursor.fetchall()
            
            if rows:
                # Find the most recent message NOT from me
                for text, rowid, is_from_me, date in rows:
                    if is_from_me == 0 and text:  # Message from them
                        conn.close()
                        return (text, rowid)
                
                # If all messages are from me, return None
                conn.close()
                return None
        
        conn.close()
        return None
        
    except Exception as e:
        # print(f"❌ Database error: {e}")
        raise Exception(f"Database error: {e}")


def wait_for_reply(recipient: str, timeout_seconds: int = 6000, poll_interval: int = 2) -> str | None:
    """
    Wait for a new message from a recipient.
    
    Args:
        recipient: Phone number or iCloud email address
        timeout_seconds: How long to wait for a reply
        poll_interval: How often to check for new messages
    
    Returns:
        The new message text, or None if timeout
    """
    print(f"⏳ Waiting for reply from {recipient} (timeout: {timeout_seconds}s)...")
    
    if TEST_MODE:
        print("🕒 TEST MODE: Sleeping 5s before setting baseline (ignoring self-text echo)...")
        time.sleep(5)
    
    # Get the current latest message rowid to compare against
    initial = get_latest_message(recipient)
    initial_rowid = initial[1] if initial else 0
    
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        current = get_latest_message(recipient)
        
        # Check if we got a new message (higher rowid = newer)
        if current and current[1] > initial_rowid:
            print(f"📩 Received: {current[0]}")
            return current[0]
        
        time.sleep(poll_interval)
    
    print("⏰ Timeout waiting for reply")
    return None
