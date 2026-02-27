#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/Users/Shared/daily-briefing"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/build.log"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"

mkdir -p "$LOG_DIR"

# Ensure output files are world-writable so both launchd (mattlerner)
# and OpenClaw (openclaw) can overwrite them.
umask 000

{
    echo "========================================="
    echo "Daily Briefing Build — $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "========================================="

    cd "$REPO_DIR"

    "$PYTHON" src/build.py "$@" 2>&1

    echo ""
    echo "Deploying to GitHub Pages..."
    OUT_DIR="$REPO_DIR/out"
    cd "$OUT_DIR"
    git init -q
    git checkout -q -b gh-pages
    git add -A
    git commit -q -m "Deploy briefings — $(date '+%Y-%m-%d')"
    git remote add origin https://github.com/mrlerner/daily-briefing.git
    git push -q -u origin gh-pages --force
    rm -rf "$OUT_DIR/.git"
    cd "$REPO_DIR"

    echo "Deploy completed at $(date '+%H:%M:%S %Z')"
} >> "$LOG_FILE" 2>&1
