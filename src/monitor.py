#!/usr/bin/env python3
"""
PollEV Monitor Script.

Runs indefinitely, joining PollEV sessions at scheduled class times
with GPS location spoofing. Logs page changes to console with timestamps.
"""
import sys
import time as time_module
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright, Page

from config import POLLEV_BASE_URL, SESSION_STATE_DIR
from utils import load_classes, get_active_class, time_until_next_class, parse_time
from gemma import ask_gemma, notify_low_confidence, AnswerStatus
from pollev_parser import extract_from_page, click_option

# Global flag for graceful shutdown
_stop_requested = False


def log(message: str) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def create_geolocation_context(playwright, class_info: dict):
    """Create a browser context with spoofed geolocation."""
    storage_path = SESSION_STATE_DIR / "state.json"
    
    if not storage_path.exists():
        raise FileNotFoundError(
            f"Session state not found at {storage_path}. "
            "Please run login.py first to save your session."
        )
    
    browser = playwright.chromium.launch(headless=False)
    
    # Note: In the JSON, "longitude" and "latitude" may be swapped
    # Typical: latitude ~42.4 (north), longitude ~-76.5 (west)
    # The JSON has longitude: 42.447083, latitude: -76.482222 which looks swapped
    # We'll use them as provided but swap if needed based on typical Cornell coordinates
    lat = class_info.get("latitude", 0)
    lon = class_info.get("longitude", 0)
    
    # Detect if they're swapped (latitude should be positive ~42, longitude negative ~-76)
    if lon > 0 and lat < 0:
        lat, lon = lon, lat  # Swap them
    
    context = browser.new_context(
        storage_state=str(storage_path),
        geolocation={"latitude": lat, "longitude": lon},
        permissions=["geolocation"],
    )
    
    return browser, context


def get_page_content_hash(page: Page) -> str:
    """Get a hash of the main content area to detect changes."""
    try:
        # Try to get the main content text
        content = page.evaluate("""
            () => {
                // Try common content selectors
                const main = document.querySelector('main') || 
                             document.querySelector('[role="main"]') ||
                             document.querySelector('.content') ||
                             document.body;
                return main ? main.innerText : '';
            }
        """)
        return str(hash(content))
    except Exception:
        return ""


def handle_poll_question(page: Page) -> None:
    """Extract question, ask Gemma, and click the best answer."""
    result = extract_from_page(page)
    if not result:
        log("⚠️  Could not extract question from page")
        return
    
    question, options = result
    log(f"❓ Question: {question}")
    log(f"   Options: {options}")
    
    # Ask Gemma
    log("🤖 Asking Gemma...")
    answer = ask_gemma(question, options)
    
    if answer.status == AnswerStatus.ERROR:
        log(f"❌ AI Error: {answer.reasoning}")
        notify_low_confidence(question, answer)
        return
    
    # Always click the best answer
    confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(answer.confidence, "⚪")
    log(f"{confidence_emoji} Answer: Option {answer.option_number} ({answer.confidence} confidence)")
    log(f"   Type: {answer.question_type}")
    log(f"   Reasoning: {answer.reasoning[:100]}...")
    
    if click_option(page, answer.option_number):
        log(f"🖱️  Clicked option {answer.option_number}: {options[answer.option_number - 1]}")
    else:
        log(f"❌ Failed to click option {answer.option_number}")
    
    # Notify if low confidence
    if answer.status == AnswerStatus.LOW_CONFIDENCE:
        notify_low_confidence(question, answer)


def monitor_page_changes(page: Page) -> None:
    """Poll for page changes and log them."""
    global _stop_requested
    last_hash = get_page_content_hash(page)
    last_url = page.url
    last_question_handled = None
    
    log("👁️  Started monitoring for page changes...")
    log("💡 Press ENTER to stop gracefully")
    
    # Try to answer initial question
    result = extract_from_page(page)
    if result:
        handle_poll_question(page)
        last_question_handled = result[0]
    
    while not _stop_requested:
        time_module.sleep(0.5)  # Check every 500ms
        
        try:
            current_url = page.url
            if current_url != last_url:
                log(f"🔄 URL changed: {last_url} → {current_url}")
                last_url = current_url
                last_hash = get_page_content_hash(page)
                last_question_handled = None  # Reset on URL change
                continue
            
            current_hash = get_page_content_hash(page)
            if current_hash != last_hash and current_hash:
                log(f"📝 Page content updated!")
                last_hash = current_hash
                
                # Check if there's a new question
                result = extract_from_page(page)
                if result and result[0] != last_question_handled:
                    handle_poll_question(page)
                    last_question_handled = result[0]
                    
        except Exception as e:
            # Page might be navigating
            log(f"⚠️  Page state change detected: {type(e).__name__}")
            break
    
    if _stop_requested:
        log("🛑 Stop requested, closing...")


def monitor_class_session(playwright, class_name: str, class_info: dict) -> None:
    """Open PollEV for a class and monitor until end time (or indefinitely if no end_time)."""
    section = class_info["section"]
    url = f"{POLLEV_BASE_URL}/{section}"
    end_time = parse_time(class_info.get("end_time", ""))
    
    log(f"🎓 Starting session for {class_name}")
    log(f"   Section: {section}")
    log(f"   URL: {url}")
    if end_time:
        log(f"   End time: {end_time}")
    else:
        log("   End time: None (running indefinitely, Ctrl+C to stop)")
    
    browser, context = create_geolocation_context(playwright, class_info)
    page = context.new_page()
    
    try:
        page.goto(url)
        log(f"📍 Opened {url} with spoofed location")
        
        # Run the polling-based change monitor
        # This blocks until an error or the page closes
        import threading
        
        def check_end_time():
            """Background thread to check end time."""
            while True:
                if end_time is not None:
                    now = datetime.now()
                    if now.time() >= end_time:
                        log(f"⏰ Class ended at {end_time}, closing session")
                        page.close()
                        return
                time_module.sleep(5)
        
        if end_time:
            end_checker = threading.Thread(target=check_end_time, daemon=True)
            end_checker.start()
        
        monitor_page_changes(page)
            
    finally:
        context.close()
        browser.close()


def main():
    """Main loop: wait for classes and monitor them."""
    global _stop_requested
    
    log("=" * 60)
    log("PollEV Monitor Started")
    log("=" * 60)
    
    classes = load_classes()
    log(f"Loaded {len(classes)} class(es): {', '.join(classes.keys())}")
    
    with sync_playwright() as playwright:
        while not _stop_requested:
            # Check if we're in an active class
            active = get_active_class(classes)
            if active:
                class_name, class_info = active
                monitor_class_session(playwright, class_name, class_info)
                # After session ends, check if stop was requested
                if _stop_requested:
                    break
                continue
            
            # Check for upcoming class
            upcoming = time_until_next_class(classes)
            if upcoming:
                class_name, seconds = upcoming
                log(f"⏳ Next class: {class_name} in {seconds/60:.1f} minutes")
                
                # Sleep until class starts (check every 30 seconds)
                sleep_time = min(seconds, 30)
                time_module.sleep(sleep_time)
            else:
                # No more classes today
                log("📅 No more classes scheduled for today. Waiting...")
                time_module.sleep(60)
    
    log("👋 Exiting...")


if __name__ == "__main__":
    import threading
    
    def input_listener():
        """Listen for Enter key to trigger graceful shutdown."""
        global _stop_requested
        try:
            input()  # Blocks until Enter
            _stop_requested = True
        except EOFError:
            pass
    
    # Start input listener in background
    listener = threading.Thread(target=input_listener, daemon=True)
    listener.start()
    
    try:
        main()
    except KeyboardInterrupt:
        _stop_requested = True
        print("\n")
        log("👋 Monitor stopped by user")
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("   Run 'python src/login.py' first to save your session.")
        sys.exit(1)

