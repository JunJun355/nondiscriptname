#!/usr/bin/env python3
"""
Sandbox script to investigate page structure after clicking an option.
Helps debugging "unclick" logic.
"""
import sys
import time
from pathlib import Path
from bs4 import BeautifulSoup

# Add src to path
SRC_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(SRC_DIR))

from playwright.sync_api import sync_playwright
import browser
from utils import load_classes
from config import POLLEV_BASE_URL

TEST_CLASS = "test0"  # Default test class
OUTPUT_FILE = Path(__file__).parent.parent.parent / "data" / "click_investigation.html"

def main():
    print("🔍 Click Investigation Sandbox")
    print("================================")
    
    classes = load_classes()
    class_info = classes.get(TEST_CLASS)
    
    if not class_info:
        print(f"❌ Class '{TEST_CLASS}' not found in classes.json")
        return

    url = f"{POLLEV_BASE_URL}/{class_info['section']}"
    print(f"🌍 Target: {url}")
    
    with sync_playwright() as p:
        print("🚀 Launching browser...")
        driver, context = browser.create_geolocation_context(p, class_info)
        page = context.new_page()
        
        try:
            page.goto(url)
            print("✓ Loaded page")
            
            print("\n⚠️  ACTION REQUIRED: Make sure a poll is active on the page.")
            input(">>> Press ENTER when ready to click Option 1... ")
            
            print("🖱️  Clicking Option 1...")
            # Using browser.py's logic or manual? Let's use manual to spy on return
            buttons = page.query_selector_all(".component-response-multiple-choice__option__vote")
            if not buttons:
                print("❌ No option buttons found! Is the poll active?")
                # Dump anyway
            else:
                buttons[0].click()
                print("✅ Clicked!")
                time.sleep(2)  # Wait for UI update/animation
            
            print("📸 Capturing page state...")
            content = page.content()
            soup = BeautifulSoup(content, "lxml")
            
            # Extract relevant part to keep file small
            # Try to find the multiple choice component container
            container = soup.select_one(".component-response-multiple-choice")
            if not container:
                print("⚠️  Could not narrow down to .component-response-multiple-choice. Saving body.")
                container = soup.body
            
            cleaned_html = container.prettify()
            
            OUTPUT_FILE.write_text(cleaned_html)
            print(f"\n💾 Saved DOM snapshot to: {OUTPUT_FILE}")
            print(f"   Size: {len(cleaned_html)} bytes")
            
            input("\n>>> Press ENTER to close browser... ")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            context.close()
            with open("temp_dump.html", "w") as f: # Backup
                f.write(page.content())
            driver.close()

if __name__ == "__main__":
    main()
