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

from playwright.sync_api import sync_playwright

from config import POLLEV_BASE_URL
from utils import load_classes, is_within_class_time, parse_time
from gemma import ask_gemma, notify_low_confidence, AnswerStatus
import browser

# Global flag for graceful shutdown
_stop_requested = False
# Track which classes have active sessions
_active_sessions = {}
_sessions_lock = threading.Lock()


def log(message: str, class_name: str = None) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = f"[{class_name}] " if class_name else ""
    print(f"[{timestamp}] {prefix}{message}")


def handle_poll_question(page, class_name: str) -> None:
    """Extract question, ask Gemma, and click the best answer."""
    result = browser.extract_from_page(page)
    if not result:
        return
    
    question, options = result
    
    # Consolidated print as requested
    log(f"Asking Gemma: Options={options} Question='{question}'", class_name)
    
    answer = ask_gemma(question, options)
    
    selected_option_index = None

    if answer.status == AnswerStatus.ERROR:
        log(f"❌ AI Error: {answer.reasoning}", class_name)
        notify_low_confidence(question, answer)
    elif answer.confidence == "low":
        log(f"🔴 Low Confidence: {answer.reasoning[:100]}...", class_name)
        notify_low_confidence(question, answer)
        selected_option_index = answer.option_number - 1
    else:
        # High/Medium confidence
        confidence_emoji = {"high": "🟢", "medium": "🟡"}.get(answer.confidence, "⚪")
        log(f"{confidence_emoji} Gemma Response: Confidence={answer.confidence}, Suggested=Option {answer.option_number}", class_name)
        selected_option_index = answer.option_number - 1

    # Legacy/Blocking iMessage block removed.
    # Flow should be: Ask Gemma -> Click Default -> Start Async Loop
    pass
            
    # Always click Gemma's answer first (even if Low Confidence) to ensure baseline participation
    if selected_option_index is not None:
        log(f"   Clicking initial AI choice: Option {selected_option_index + 1}...", class_name)
        if browser.click_option(page, selected_option_index + 1):
             pass
        else:
             log(f"❌ Failed to click option {selected_option_index + 1}", class_name)

    # iMessage fallback loop (if needed)
    if answer.confidence == "low" or answer.status == AnswerStatus.ERROR:
        try:
            from imessage import load_config, send_message, get_latest_message
            config = load_config()
            recipient = config.get("recipient_address")
            
            if recipient:
                # Format message
                msg_text = f"PollEV Help!\nQ: {question}\n"
                for i, opt in enumerate(options):
                    msg_text += f"{i+1}. {opt}\n"
                msg_text += f"Reply with 1-{len(options)}"
                
                if send_message(recipient, msg_text):
                    log(f"📱 Sent iMessage to {recipient}", class_name)
                    
                    # Enter loop to allow changing answer until question ends
                    initial_hash = browser.get_page_content_hash(page)
                    
                    # Get baseline message ID to ignore old messages
                    latest = get_latest_message(recipient)
                    last_seen_rowid = latest[1] if latest else 0
                    
                    log(f"⏳ Waiting for replies from {recipient} (loops until next question)...", class_name)
                    
                    while not _stop_requested:
                        # 1. Check if page changed (question ended)
                        current_hash = browser.get_page_content_hash(page)
                        if current_hash != initial_hash:
                            log("🔄 Page content changed, stopping iMessage listener.", class_name)
                            break
                            
                        # 2. Check for NEW messages
                        current_msg = get_latest_message(recipient)
                        if current_msg and current_msg[1] > last_seen_rowid:
                            reply = current_msg[0]
                            last_seen_rowid = current_msg[1]
                            
                            log(f"📩 Received: {reply}", class_name)
                            
                            if reply.strip().isdigit():
                                choice = int(reply.strip())
                                if 1 <= choice <= len(options):
                                    log(f"📩 Friend replied: Option {choice}", class_name)
                                    
                                    # Always try to unclick previous before clicking new (no index check needed)
                                    log(f"   Unclicking previous selection(s)...", class_name)
                                    browser.unclick_current_option(page)
                                    
                                    # Click new
                                    log(f"   Clicking option {choice}...", class_name)
                                    if browser.click_option(page, choice):
                                         log(f"✅ Changed answer to Option {choice}", class_name)
                                         selected_option_index = choice - 1 # Update selected_option_index
                                    else:
                                         log(f"❌ Failed to click option {choice}", class_name)
                                else:
                                    log(f"⚠️ Invalid choice: {choice}", class_name)
                        
                        time_module.sleep(2)
            else:
                log("⚠️ No iMessage recipient configured", class_name)
                
        except Exception as e:
            log(f"❌ iMessage error: {e}", class_name)


def monitor_page_changes(page, class_name: str, class_info: dict) -> None:
    """Poll for page changes and handle new questions."""
    global _stop_requested
    last_hash = browser.get_page_content_hash(page)
    last_url = page.url
    last_question_handled = None
    end_time = parse_time(class_info.get("end_time", ""))
    
    # Try to answer initial question
    result = browser.extract_from_page(page)
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
                # log(f"🔄 URL changed", class_name)
                last_url = current_url
                last_hash = browser.get_page_content_hash(page)
                last_question_handled = None
                continue
            
            current_hash = browser.get_page_content_hash(page)
            if current_hash != last_hash and current_hash:
                # log(f"📝 Page content updated", class_name)
                last_hash = current_hash
                
                result = browser.extract_from_page(page)
                if result:
                    if result[0] != last_question_handled:
                        handle_poll_question(page, class_name)
                        last_question_handled = result[0]
                else:
                    # Question disappeared (poll closed/changed), reset state
                    last_question_handled = None
                    
        except Exception as e:
            log(f"⚠️  Page state change: {type(e).__name__}", class_name)
            break


def run_class_session(class_name: str, class_info: dict) -> None:
    """Run a single class session in its own thread with its own Playwright instance."""
    global _stop_requested, _active_sessions
    
    section = class_info["section"]
    url = f"{POLLEV_BASE_URL}/{section}"
    
    log(f"🎓 Starting session (Section: {section})", class_name)
    
    try:
        with sync_playwright() as playwright:
            driver, context = browser.create_geolocation_context(playwright, class_info)
            page = context.new_page()
            
            try:
                page.goto(url)
                # log(f"📍 Opened with spoofed location", class_name)
                
                monitor_page_changes(page, class_name, class_info)
                
            finally:
                context.close()
                driver.close()
                
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
    log("💡 Type 'exit' and press ENTER to stop all sessions gracefully")
    
    classes = load_classes()
    log(f"Loaded {len(classes)} class(es): {', '.join(classes.keys())}")
    
    while not _stop_requested:
        # Get all currently active classes
        active_classes = get_all_active_classes(classes)
        
        # Start sessions for any active classes that aren't already running
        for class_name, class_info in active_classes:
            start_class_session(class_name, class_info)
        
        # Log status periodically is removed to reduce chatter
        # just waiting...
        
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
        """Listen for 'exit' command to trigger graceful shutdown."""
        global _stop_requested
        print("   (Type 'exit' and press Enter to stop)")
        try:
            while not _stop_requested:
                cmd = input()
                if cmd.strip().lower() in ["exit", "quit", "stop"]:
                    _stop_requested = True
                    break
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
