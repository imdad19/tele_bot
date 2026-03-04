#!/bin/bash
# Istanbul Market Bot — One-click launcher

echo "🛍️  Istanbul Market Explorer Bot"
echo "================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install from https://python.org"
    exit 1
fi

# Install dependencies if needed
if ! python3 -c "import telegram" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Check if token.json exists
if [ ! -f "token.json" ]; then
    echo ""
    echo "🔑 First time setup — authorizing Google Sheets..."
    python3 authorize.py
    echo ""
fi

# Check .env has sheet ID
if grep -q "PASTE_YOUR_SHEET_ID_HERE" .env; then
    echo ""
    echo "⚠️  Please set your GOOGLE_SHEET_ID in the .env file first!"
    echo "   It's the part in your Sheet URL: /spreadsheets/d/THIS_PART/edit"
    exit 1
fi

echo "🚀 Starting bot..."
python3 bot.py
