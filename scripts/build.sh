#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/Users/Shared/daily-briefing"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/build.log"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"

mkdir -p "$LOG_DIR"

{
    echo "========================================="
    echo "Daily Briefing Build — $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "========================================="

    cd "$REPO_DIR"

    "$PYTHON" src/build.py 2>&1

    echo ""
    echo "Build completed at $(date '+%H:%M:%S %Z')"
} >> "$LOG_FILE" 2>&1
