#!/usr/bin/env python3
"""
PollEV Monitor Script - Multi-Class Concurrent Version.

Runs indefinitely, opening multiple browser sessions for all active classes
simultaneously. Each browser auto-closes when its class ends.
"""
import sys
import time as time_module
import threading
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright, Page

from config import POLLEV_BASE_URL, SESSION_STATE_DIR
from utils import load_classes, is_within_class_time, parse_time
from gemma import ask_gemma, notify_low_confidence, AnswerStatus
from pollev_parser import extract_from_page, click_option

# Global flag for graceful shutdown
_stop_requested = False
# Track which classes have active sessions
_active_sessions = {}
_sessions_lock = threading.Lock()


def log(message: str, class_name: str = None) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    prefix = f"[{class_name}] " if class_name else ""
    print(f"[{timestamp}] {prefix}{message}")


def create_geolocation_context(playwright, class_info: dict):
    """Create a browser context with spoofed geolocation."""
    storage_path = SESSION_STATE_DIR / "state.json"
    
    if not storage_path.exists():
        raise FileNotFoundError(
            f"Session state not found at {storage_path}. "
            "Please run login.py first to save your session."
        )
    
    browser = playwright.chromium.launch(headless=False)
    
    lat = class_info.get("latitude", 0)
    lon = class_info.get("longitude", 0)
    
    # Detect if they're swapped (latitude should be positive ~42, longitude negative ~-76)
    if lon > 0 and lat < 0:
        lat, lon = lon, lat
    
    context = browser.new_context(
        storage_state=str(storage_path),
        geolocation={"latitude": lat, "longitude": lon},
        permissions=["geolocation"],
    )
    
    return browser, context


def get_page_content_hash(page: Page) -> str:
    """Get a hash of the main content area to detect changes."""
    try:
        content = page.evaluate("""
            () => {
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


def handle_poll_question(page: Page, class_name: str) -> None:
    """Extract question, ask Gemma, and click the best answer."""
    result = extract_from_page(page)
    if not result:
        log("⚠️  Could not extract question from page", class_name)
        return
    
    question, options = result
    log(f"❓ Question: {question}", class_name)
    log(f"   Options: {options}", class_name)
    
    log("🤖 Asking Gemma...", class_name)
    answer = ask_gemma(question, options)
    
    if answer.status == AnswerStatus.ERROR:
        log(f"❌ AI Error: {answer.reasoning}", class_name)
        notify_low_confidence(question, answer)
        return
    
    confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(answer.confidence, "⚪")
    log(f"{confidence_emoji} Answer: Option {answer.option_number} ({answer.confidence} confidence)", class_name)
    log(f"   Type: {answer.question_type}", class_name)
    log(f"   Reasoning: {answer.reasoning[:100]}...", class_name)
    
    if click_option(page, answer.option_number):
        log(f"🖱️  Clicked option {answer.option_number}: {options[answer.option_number - 1]}", class_name)
    else:
        log(f"❌ Failed to click option {answer.option_number}", class_name)
    
    if answer.status == AnswerStatus.LOW_CONFIDENCE:
        notify_low_confidence(question, answer)


def monitor_page_changes(page: Page, class_name: str, class_info: dict) -> None:
    """Poll for page changes and handle new questions."""
    global _stop_requested
    last_hash = get_page_content_hash(page)
    last_url = page.url
    last_question_handled = None
    end_time = parse_time(class_info.get("end_time", ""))
    
    log("👁️  Started monitoring for page changes...", class_name)
    
    # Try to answer initial question
    result = extract_from_page(page)
    if result:
        handle_poll_question(page, class_name)
        last_question_handled = result[0]
    
    while not _stop_requested:
        # Check if class has ended
        if end_time is not None:
            now = datetime.now().time()
            if now >= end_time:
                log(f"⏰ Class ended at {end_time}", class_name)
                return
        
        time_module.sleep(0.5)
        
        try:
            current_url = page.url
            if current_url != last_url:
                log(f"🔄 URL changed: {last_url} → {current_url}", class_name)
                last_url = current_url
                last_hash = get_page_content_hash(page)
                last_question_handled = None
                continue
            
            current_hash = get_page_content_hash(page)
            if current_hash != last_hash and current_hash:
                log(f"📝 Page content updated!", class_name)
                last_hash = current_hash
                
                result = extract_from_page(page)
                if result and result[0] != last_question_handled:
                    handle_poll_question(page, class_name)
                    last_question_handled = result[0]
                    
        except Exception as e:
            log(f"⚠️  Page state change: {type(e).__name__}", class_name)
            break


def run_class_session(class_name: str, class_info: dict) -> None:
    """Run a single class session in its own thread with its own Playwright instance."""
    global _stop_requested, _active_sessions
    
    section = class_info["section"]
    url = f"{POLLEV_BASE_URL}/{section}"
    
    log(f"🎓 Starting session", class_name)
    log(f"   Section: {section}", class_name)
    log(f"   URL: {url}", class_name)
    
    try:
        with sync_playwright() as playwright:
            browser, context = create_geolocation_context(playwright, class_info)
            page = context.new_page()
            
            try:
                page.goto(url)
                log(f"📍 Opened with spoofed location", class_name)
                
                monitor_page_changes(page, class_name, class_info)
                
            finally:
                context.close()
                browser.close()
                
    except Exception as e:
        log(f"❌ Session error: {e}", class_name)
    
    finally:
        with _sessions_lock:
            _active_sessions.pop(class_name, None)
        log(f"👋 Session closed", class_name)


def start_class_session(class_name: str, class_info: dict) -> None:
    """Start a class session in a new thread if not already running."""
    global _active_sessions
    
    with _sessions_lock:
        if class_name in _active_sessions:
            return  # Already running
        
        thread = threading.Thread(
            target=run_class_session,
            args=(class_name, class_info),
            daemon=True
        )
        _active_sessions[class_name] = thread
        thread.start()


def get_all_active_classes(classes: dict) -> list[tuple[str, dict]]:
    """Get all classes that are currently within their scheduled time."""
    active = []
    for class_name, class_info in classes.items():
        if is_within_class_time(class_info):
            active.append((class_name, class_info))
    return active


def main():
    """Main loop: continuously check for active classes and spawn sessions."""
    global _stop_requested
    
    log("=" * 60)
    log("PollEV Multi-Class Monitor Started")
    log("=" * 60)
    log("💡 Press ENTER to stop all sessions gracefully")
    
    classes = load_classes()
    log(f"Loaded {len(classes)} class(es): {', '.join(classes.keys())}")
    
    while not _stop_requested:
        # Get all currently active classes
        active_classes = get_all_active_classes(classes)
        
        # Start sessions for any active classes that aren't already running
        for class_name, class_info in active_classes:
            start_class_session(class_name, class_info)
        
        # Log status periodically
        with _sessions_lock:
            if _active_sessions:
                pass  # Sessions are running, just keep checking
            elif not active_classes:
                # Find next class
                next_class = None
                next_seconds = float('inf')
                now = datetime.now()
                
                for name, info in classes.items():
                    start = parse_time(info.get("start_time", ""))
                    if start:
                        start_dt = now.replace(
                            hour=start.hour, minute=start.minute, second=start.second, microsecond=0
                        )
                        if start_dt > now:
                            diff = (start_dt - now).total_seconds()
                            if diff < next_seconds:
                                next_seconds = diff
                                next_class = name
                
                if next_class and next_seconds < float('inf'):
                    log(f"⏳ Next class: {next_class} in {next_seconds/60:.1f} minutes")
                else:
                    log("📅 No more classes scheduled. Waiting...")
        
        time_module.sleep(10)  # Check every 10 seconds
    
    # Wait for all sessions to close
    log("🛑 Shutdown requested, waiting for sessions to close...")
    with _sessions_lock:
        threads = list(_active_sessions.values())
    
    for t in threads:
        t.join(timeout=5)
    
    log("👋 All sessions closed. Exiting...")


if __name__ == "__main__":
    def input_listener():
        """Listen for Enter key to trigger graceful shutdown."""
        global _stop_requested
        try:
            input()
            _stop_requested = True
        except EOFError:
            pass
    
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
