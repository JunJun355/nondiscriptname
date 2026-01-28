#!/usr/bin/env python3
"""
PollEV HTML parser for extracting questions and options.
"""
from bs4 import BeautifulSoup
from playwright.sync_api import Page


def extract_from_html(html_content: str) -> tuple[str, list[str]] | None:
    """
    Extract question and options from PollEV HTML.
    
    Returns:
        Tuple of (question, options) or None if not found
    """
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


def extract_from_page(page: Page) -> tuple[str, list[str]] | None:
    """
    Extract question and options directly from a Playwright page.
    
    Returns:
        Tuple of (question, options) or None if not found
    """
    html_content = page.content()
    return extract_from_html(html_content)


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
