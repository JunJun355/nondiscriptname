#!/usr/bin/env python3
"""
PollEV AI Answerer using Gemma 3 27B.

Extracts question and options from PollEV HTML and uses AI to determine the best answer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup
import google.generativeai as genai
from config import DATA_DIR


def extract_question_and_options(html_path: Path) -> tuple[str, list[str]] | None:
    """Extract question and options from PollEV HTML file."""
    if not html_path.exists():
        print(f"❌ HTML file not found: {html_path}")
        return None
    
    soup = BeautifulSoup(html_path.read_text(), "lxml")
    
    # Extract question title
    title_elem = soup.select_one(".component-response-header__title")
    if not title_elem:
        print("❌ Could not find question title in HTML")
        return None
    question = title_elem.get_text(strip=True)
    
    # Extract options
    option_elems = soup.select(".component-response-multiple-choice__option__value")
    if not option_elems:
        print("❌ Could not find options in HTML")
        return None
    options = [opt.get_text(strip=True) for opt in option_elems]
    
    return question, options


def build_prompt(question: str, options: list[str]) -> str:
    """Build the prompt for Gemma."""
    options_text = "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(options))
    
    return f"""You are answering a multiple choice poll question. Your task is to select the BEST answer.

QUESTION: {question}

OPTIONS:
{options_text}

INSTRUCTIONS:
1. If this is a factual question with a clear correct answer, respond with:
   ANSWER: [option number]
   REASON: [brief explanation]

2. If the question requires OUTSIDE KNOWLEDGE that you cannot verify (e.g., "What did the professor say?", "What was discussed in class?"), respond with:
   CANNOT_ANSWER: REQUIRES_OUTSIDE_KNOWLEDGE
   REASON: [explain what knowledge is missing]

3. If the question is SUBJECTIVE with no correct answer (e.g., opinion-based), respond with:
   CANNOT_ANSWER: SUBJECTIVE
   REASON: [explain why it's subjective]

Now analyze the question and provide your response:"""


def ask_gemma(prompt: str) -> str:
    """Send prompt to Gemma 3 27B and get response."""
    api_key_file = DATA_DIR / "API_KEY_GEMINI"
    if not api_key_file.exists():
        raise FileNotFoundError(f"API key not found at {api_key_file}")
    
    api_key = api_key_file.read_text().strip()
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel("gemma-3-27b-it")
    response = model.generate_content(prompt)
    return response.text


def main():
    html_path = DATA_DIR / "pollev_page.html"
    
    print("=" * 60)
    print("PollEV AI Answerer (Gemma 3 27B)")
    print("=" * 60)
    
    # Extract question and options
    result = extract_question_and_options(html_path)
    if not result:
        sys.exit(1)
    
    question, options = result
    
    print(f"\n📝 QUESTION: {question}")
    print("\n📋 OPTIONS:")
    for i, opt in enumerate(options):
        print(f"   {i+1}. {opt}")
    
    # Build and send prompt
    prompt = build_prompt(question, options)
    
    print("\n" + "-" * 60)
    print("🤖 Asking Gemma 3 27B...")
    print("-" * 60)
    
    try:
        response = ask_gemma(prompt)
        print(f"\n💬 GEMMA RESPONSE:\n{response}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
