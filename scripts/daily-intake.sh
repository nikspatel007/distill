#!/bin/bash
# Daily intake digest — runs via launchd
# Fetches RSS feeds, enriches content, synthesizes digest, writes to Obsidian

set -euo pipefail

# Paths
PROJECT_DIR="/Users/nikpatel/Documents/GitHub/distill"
OUTPUT_DIR="/Users/nikpatel/Documents/Obsidian Vault"
LOG_DIR="$HOME/.local/log/distill"
UV="/opt/homebrew/bin/uv"

# Ensure log dir exists
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/intake-$(date +%Y-%m-%d).log"

{
    echo "=== Distill Daily Intake — $(date) ==="

    cd "$PROJECT_DIR"

    # Run the intake pipeline
    "$UV" run python -m distill intake \
        --output "$OUTPUT_DIR" \
        --use-defaults \
        2>&1

    echo "=== Completed — $(date) ==="

    # macOS notification on success
    osascript -e 'display notification "Daily research digest is ready in Obsidian" with title "Distill"' 2>/dev/null || true

} >> "$LOG_FILE" 2>&1

# Clean up logs older than 30 days
find "$LOG_DIR" -name "intake-*.log" -mtime +30 -delete 2>/dev/null || true
