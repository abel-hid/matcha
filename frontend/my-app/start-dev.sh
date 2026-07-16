#!/bin/bash

# Load nvm (if not already loaded)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Check if nvm is available
if ! command -v nvm &> /dev/null; then
    echo "❌ nvm not found. Please install nvm first:"
    echo "   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash"
    exit 1
fi

echo "✅ nvm loaded successfully"

# Install Node.js 22 (LTS) if not already installed
echo "📦 Installing Node.js 22..."
nvm install 22

# Switch to Node.js 22
echo "🔄 Switching to Node.js 22..."
nvm use 22

# Set as default (optional)
nvm alias default 22

# Verify version
echo "🔍 Node version: $(node --version)"
echo "🔍 npm version: $(npm --version)"

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "📦 Installing npm dependencies..."
    npm install
fi

echo "🚀 Starting Next.js dev server..."
npm run dev