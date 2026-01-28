#!/bin/bash
set -e

echo "📦 Setting up environment..."

# Create venv if not exists
if [ ! -d ".venv" ]; then
    echo "   Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
echo "   Activating venv..."
source .venv/bin/activate

# Install dependencies
echo "   Installing Python packages..."
# pip install --upgrade pip
pip install playwright google-generativeai beautifulsoup4 lxml

# Install Playwright browsers (chromium only)
echo "   Installing Playwright Chromium..."
playwright install chromium

echo "✅ Environment setup complete!"
echo "   To start using it, run: source .venv/bin/activate"
