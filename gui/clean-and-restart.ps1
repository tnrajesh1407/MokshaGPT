# Clean and Restart Script for Windows PowerShell
# This script cleans the Next.js build cache and restarts the dev server

Write-Host "🧹 Cleaning Next.js build cache..." -ForegroundColor Cyan

# Stop any running processes on port 3000
$processes = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
if ($processes) {
    Write-Host "⚠️  Port 3000 is in use. Please stop the dev server first (Ctrl+C)" -ForegroundColor Yellow
    Write-Host "Then run this script again." -ForegroundColor Yellow
    exit 1
}

# Remove .next directory
if (Test-Path ".next") {
    Write-Host "Removing .next directory..." -ForegroundColor Yellow
    Remove-Item -Path ".next" -Recurse -Force -ErrorAction SilentlyContinue
    
    # If removal failed, try again with more aggressive approach
    if (Test-Path ".next") {
        Write-Host "First attempt failed, trying alternative method..." -ForegroundColor Yellow
        Get-ChildItem -Path ".next" -Recurse | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
        Remove-Item -Path ".next" -Force -ErrorAction SilentlyContinue
    }
    
    if (Test-Path ".next") {
        Write-Host "❌ Could not remove .next directory. Please close all applications using these files." -ForegroundColor Red
        exit 1
    }
}

Write-Host "✅ Build cache cleaned!" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Starting dev server..." -ForegroundColor Cyan
Write-Host ""

# Start dev server
npm run dev
