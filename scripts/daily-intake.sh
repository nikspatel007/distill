#!/bin/bash
# Daily distill pipeline — runs via launchd/cron
# Sessions -> Journal -> Intake -> Blog -> Obsidian
#
# Usage:
#   1. Copy this script and customize the paths below
#   2. Set up a launchd plist (macOS) or cron job (Linux)
#   3. See README.md for launchd/cron configuration examples

set -euo pipefail

# ─── Customize these paths ────────────────────────────────────────
PROJECT_DIR="${DISTILL_PROJECT_DIR:-$HOME/distill}"
OUTPUT_DIR="${DISTILL_OUTPUT_DIR:-$HOME/insights}"
UV="${DISTILL_UV_PATH:-$(command -v uv || echo /opt/homebrew/bin/uv)}"
# ──────────────────────────────────────────────────────────────────

LOG_DIR="$HOME/.local/log/distill"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/distill-$(date +%Y-%m-%d).log"

{
    echo "=== Distill Daily Run — $(date) ==="

    cd "$PROJECT_DIR"

    # Run the full pipeline: sessions -> journal -> intake -> blog
    "$UV" run python -m distill run \
        --dir "$HOME" \
        --output "$OUTPUT_DIR" \
        --use-defaults \
        --publish obsidian \
        2>&1

    echo "=== Completed — $(date) ==="

    # macOS notification on success (comment out on Linux)
    osascript -e 'display notification "Daily digest ready" with title "Distill"' \
        2>/dev/null || true

} >> "$LOG_FILE" 2>&1

# Clean up logs older than 30 days
find "$LOG_DIR" -name "distill-*.log" -mtime +30 -delete 2>/dev/null || true
