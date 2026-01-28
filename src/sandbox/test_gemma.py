#!/usr/bin/env python3
"""
Test script for Gemma 3 27B via Google's Generative AI API.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import google.generativeai as genai
from config import DATA_DIR


def main():
    # Load API key
    api_key_file = DATA_DIR / "API_KEY_GEMINI"
    if not api_key_file.exists():
        print(f"❌ API key not found at {api_key_file}")
        sys.exit(1)
    
    api_key = api_key_file.read_text().strip()
    genai.configure(api_key=api_key)
    
    # Use Gemma 3 27B
    model_name = "gemma-3-27b-it"
    print(f"🤖 Testing model: {model_name}")
    print("=" * 50)
    
    try:
        model = genai.GenerativeModel(model_name)
        
        # Simple test question
        prompt = "How many r's are in strrawberry?"
        print(f"📝 Prompt: {prompt}")
        print("-" * 50)
        
        response = model.generate_content(prompt)
        print(f"💬 Response: {response.text}")
        print("=" * 50)
        print("✅ Gemma 3 27B is working!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
