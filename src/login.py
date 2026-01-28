#!/usr/bin/env python3
"""
Login script for PollEV.

This script opens a browser window for manual login, then saves the session
state to be reused by the monitor script.
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright

from config import POLLEV_LOGIN_URL, SESSION_STATE_DIR


def main():
    """Open browser for login and save session state."""
    storage_path = SESSION_STATE_DIR / "state.json"
    
    print("=" * 60)
    print("PollEV Login Session Saver")
    print("=" * 60)
    print()
    print("A browser window will open. Please log in to PollEV.")
    print("Once logged in, press ENTER in this terminal to save the session.")
    print()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to login page
        page.goto(POLLEV_LOGIN_URL)
        print(f"Navigated to: {POLLEV_LOGIN_URL}")
        print()
        
        # Wait for user to complete login
        input(">>> Press ENTER after you have logged in successfully... ")
        
        # Save storage state (cookies, localStorage, etc.)
        context.storage_state(path=str(storage_path))
        print()
        print(f"✓ Session saved to: {storage_path}")
        print("  You can now run monitor.py to automate PollEV attendance.")
        
        browser.close()


if __name__ == "__main__":
    main()
