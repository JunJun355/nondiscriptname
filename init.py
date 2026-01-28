#!/usr/bin/env python3
"""
Interactive setup script for PollEV Automation.
Helps configure API keys, iMessage settings, and Class schedules.
"""
import json
import sys
from pathlib import Path
from typing import Any

# Paths
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"

API_KEY_FILE = DATA_DIR / "API_KEY_GEMINI"
IMESSAGE_FILE = DATA_DIR / "imessage_config.json"
CLASSES_FILE = DATA_DIR / "classes.json"


def input_with_default(prompt_text: str, current_value: Any = "") -> str:
    """Prompt user with a default value shown in brackets."""
    display_val = str(current_value)
    if len(display_val) > 50:
        display_val = display_val[:47] + "..."
    
    prompt_str = f"{prompt_text} [{display_val}]: "
    user_input = input(prompt_str).strip()
    return user_input if user_input else str(current_value)


def setup_api_key():
    print("\n--- Gemma API Key ---")
    current_key = ""
    exists = False
    if API_KEY_FILE.exists():
        current_key = API_KEY_FILE.read_text().strip()
        exists = True if current_key else False
    
    if exists:
        prompt_txt = "Enter Gemini API Key [********] (Press Enter to keep)"
        new_key = input(f"{prompt_txt}: ").strip()
        if not new_key:
            print("✓ Kept existing API Key.")
            return
    else:
        new_key = ""
        while not new_key:
            new_key = input("Enter Gemini API Key: ").strip()
            if not new_key:
                print("❌ Key is required!")
    
    if new_key:
        API_KEY_FILE.write_text(new_key)
        print("✓ API Key saved.")


def setup_imessage():
    print("\n--- iMessage Configuration ---")
    config = {}
    if IMESSAGE_FILE.exists():
        try:
            config = json.loads(IMESSAGE_FILE.read_text())
        except json.JSONDecodeError:
            pass
            
    # Allow empty/partial config
    current_recipient = config.get("recipient_address", "")
    
    new_recipient = input_with_default("iMessage Recipient (Phone/Email)", current_recipient)
    
    if new_recipient:
        config["recipient_address"] = new_recipient
        IMESSAGE_FILE.write_text(json.dumps(config, indent=2))
        print("✓ iMessage config updated.")
    else:
        print("✓ No changes to iMessage config.")


def setup_classes():
    print("\n--- Class Configuration ---")
    classes = {}
    if CLASSES_FILE.exists():
        try:
            classes = json.loads(CLASSES_FILE.read_text())
        except json.JSONDecodeError:
            pass
            
    print(f"Current classes: {', '.join(classes.keys()) if classes else 'None'}")
    
    while True:
        mode = input("\nDo you want to (E)dit/Add a class, or (F)inish? [F]: ").strip().lower()
        if mode != 'e':
            break
            
        class_name = input("Enter Class Name (e.g., 'CS 101'): ").strip()
        if not class_name:
            continue
            
        # Get existing details if updating
        current_info = classes.get(class_name, {})
        
        print(f"\nConfiguring '{class_name}':")
        
        section = input_with_default("  PollEV Section (URL part)", current_info.get("section", ""))
        
        # Location
        lat = input_with_default("  Latitude", current_info.get("latitude", 0))
        try:
            lat = float(lat)
        except ValueError:
            lat = 0
            
        lon = input_with_default("  Longitude", current_info.get("longitude", 0))
        try:
            lon = float(lon)
        except ValueError:
            lon = 0
            
        # Time
        start = input_with_default("  Start Time (HH:MM:SS)", current_info.get("start_time", "09:00:00"))
        end = input_with_default("  End Time (HH:MM:SS)", current_info.get("end_time", "10:15:00"))
        
        # Save to dict
        classes[class_name] = {
            "section": section,
            "latitude": lat,
            "longitude": lon,
            "start_time": start,
            "end_time": end
        }
        
        # Write immediately
        CLASSES_FILE.write_text(json.dumps(classes, indent=2))
        print(f"✓ Saved '{class_name}' to classes.json")


import subprocess

def setup_dependencies():
    print("\n--- Dependencies ---")
    if input_with_default("Run setup.sh to install/update dependencies? (Y/n)", "Y").lower() == 'y':
        try:
            # Check for setup.sh
            setup_script = BASE_DIR / "src" / "setup.sh"
            if not setup_script.exists():
                print("❌ setup.sh not found!")
                return
                
            subprocess.run(["bash", str(setup_script)], check=True)
        except subprocess.CalledProcessError:
            print("❌ Setup failed.")
        except Exception as e:
            print(f"❌ Error running setup: {e}")
    else:
        print("✓ Skipping dependency setup.")


def main():
    print("🛠️  PollEV Automation Setup (init.py)")
    print("=" * 40)
    
    # Ensure data dir exists
    DATA_DIR.mkdir(exist_ok=True)
    
    try:
        setup_dependencies()
        setup_api_key()
        setup_imessage()
        setup_classes()
        print("\n✅ Setup complete! Don't forget to 'source .venv/bin/activate' before running.")
        print("   Then run: 'python run.py'")
        
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled.")
        sys.exit(1)

if __name__ == "__main__":
    main()
