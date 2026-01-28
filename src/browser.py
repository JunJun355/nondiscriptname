"""
Browser automation and interaction logic.
Handles browser creation, location spoofing, content extraction, and interaction.
"""
from bs4 import BeautifulSoup
from playwright.sync_api import Page, Playwright, Browser, BrowserContext

from config import SESSION_STATE_DIR

def create_geolocation_context(playwright: Playwright, class_info: dict) -> tuple[Browser, BrowserContext]:
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


def extract_from_page(page: Page) -> tuple[str, list[str]] | None:
    """
    Extract question and options directly from a Playwright page.
    
    Returns:
        Tuple of (question, options) or None if not found
    """
    try:
        html_content = page.content()
        soup = BeautifulSoup(html_content, "lxml")
        
        # Extract question title
        title_elem = soup.select_one(".component-response-header__title")
        if not title_elem:
            return None
        question = title_elem.get_text(strip=True)
        
        # Extract options
        option_elems = soup.select(".component-response-multiple-choice__option__value")
        if not option_elems:
            return None
        options = [opt.get_text(strip=True) for opt in option_elems]
        
        return question, options
    except Exception:
        return None


def click_option(page: Page, option_number: int) -> bool:
    """
    Click the specified option button (1-indexed).
    
    Returns:
        True if click succeeded, False otherwise
    """
    try:
        # Get all vote buttons
        buttons = page.query_selector_all(".component-response-multiple-choice__option__vote")
        if option_number < 1 or option_number > len(buttons):
            return False
        
        # Click the button (0-indexed internally)
        buttons[option_number - 1].click()
        return True
    except Exception:
        return False


def unclick_current_option(page: Page) -> bool:
    """
    Find and click 'undo' buttons for ANY currently selected options.
    Returns True if at least one undo button was clicked.
    """
    try:
        undo_buttons = page.query_selector_all(".component-response-multiple-choice__option__undo")
        clicked_any = False
        
        for btn in undo_buttons:
            if btn.is_visible():
                btn.click()
                clicked_any = True
                # Keep going to clear ALL selections (safe for multi-select too)
                
        return clicked_any
    except Exception:
        return False
