#!/usr/bin/env python3
"""
Capture PollEV page HTML for analysis.
Opens PollEV using saved session and saves the page HTML to data/.
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright
from config import POLLEV_BASE_URL, SESSION_STATE_DIR, DATA_DIR
from utils import load_classes


def main():
    classes = load_classes()
    if not classes:
        print("❌ No classes found in classes.json")
        sys.exit(1)
    
    # Get first class
    class_name, class_info = next(iter(classes.items()))
    section = class_info["section"]
    url = f"{POLLEV_BASE_URL}/{section}"
    
    storage_path = SESSION_STATE_DIR / "state.json"
    if not storage_path.exists():
        print(f"❌ Session not found. Run login.py first.")
        sys.exit(1)
    
    print(f"🌐 Opening {url}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(storage_path))
        page = context.new_page()
        
        page.goto(url)
        print("⏳ Waiting for page to load (5 seconds)...")
        page.wait_for_timeout(5000)
        
        # Save HTML
        html_content = page.content()
        output_file = DATA_DIR / "pollev_page.html"
        output_file.write_text(html_content)
        
        file_size = output_file.stat().st_size
        file_size_kb = file_size / 1024
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"✅ Saved HTML to: {output_file}")
        print(f"📊 File size: {file_size:,} bytes ({file_size_kb:.1f} KB / {file_size_mb:.2f} MB)")
        
        if file_size_kb > 100:
            print("⚠️  File is relatively large - may need cleaning")
        
        browser.close()


if __name__ == "__main__":
    main()
