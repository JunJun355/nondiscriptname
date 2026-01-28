#!/usr/bin/env python3
"""
Launcher script for PollEV skipping automation.
Checks if login is valid, then starts the monitor.
"""
import os
import sys
import subprocess
from pathlib import Path

# Constants matching config.py logic
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
SESSION_STATE_DIR = DATA_DIR / "session_state"
SESSION_FILE = SESSION_STATE_DIR / "state.json"

def main():
    print("🚀 PollEV Automation Launcher")
    print("=" * 30)
    
    # Check if session exists
    if not SESSION_FILE.exists():
        print("⚠️  No session found. Starting login flow...")
        try:
            subprocess.run([sys.executable, "src/login.py"], check=True)
        except subprocess.CalledProcessError:
            print("❌ Login failed or cancelled.")
            sys.exit(1)
            
        # Verify it was created
        if not SESSION_FILE.exists():
            print("❌ Session file still missing after login. Exiting.")
            sys.exit(1)
    else:
        print("✅ Session found.")

    # Run monitor
    print("👁️  Starting monitor...")
    try:
        # Pass through any arguments (like -test) to the monitor
        args = [sys.executable, "src/monitor.py"] + sys.argv[1:]
        subprocess.run(args, check=True)
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError:
        print("❌ Monitor exited with error.")

if __name__ == "__main__":
    main()
