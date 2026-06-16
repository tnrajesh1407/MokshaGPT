#!/bin/bash
# Clean and Restart Script for Linux/Mac
# This script cleans the Next.js build cache and restarts the dev server

echo "🧹 Cleaning Next.js build cache..."

# Check if port 3000 is in use
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 3000 is in use. Please stop the dev server first (Ctrl+C)"
    echo "Then run this script again."
    exit 1
fi

# Remove .next directory
if [ -d ".next" ]; then
    echo "Removing .next directory..."
    rm -rf .next
    
    if [ -d ".next" ]; then
        echo "❌ Could not remove .next directory. Please close all applications using these files."
        exit 1
    fi
fi

echo "✅ Build cache cleaned!"
echo ""
echo "🚀 Starting dev server..."
echo ""

# Start dev server
npm run dev
