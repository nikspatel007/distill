#!/bin/bash
# pre-signal-check.sh - Run before signal_workflow(done)
#
# This script enforces the "fresh verification before signaling" rule
# learned from Cycle 2, where 0% KPIs reflected signaling failure
# (work existed but signals never fired because verification was skipped).
#
# Cycle 4 addition: Now verifies deliverables are tracked in git.
# This closes the verification gap that caused 4 consecutive failures
# where code existed in worktrees but was never committed.
#
# Usage: .vermas/scripts/pre-signal-check.sh [deliverable1] [deliverable2] ...
# Exit codes:
#   0 = Ready to signal done
#   1 = Verification failed, do NOT signal

set -e

DELIVERABLE_COUNT=$#
if [ $DELIVERABLE_COUNT -gt 0 ]; then
    TOTAL_STEPS=3
else
    TOTAL_STEPS=2
fi

echo "=== Pre-Signal Verification ==="
echo ""

# 1. Run tests
echo "[1/$TOTAL_STEPS] Running pytest..."
if ! uv run pytest tests/ -q; then
    echo ""
    echo "FAIL: Tests not passing"
    echo "Fix failing tests before signaling done."
    exit 1
fi
echo "Tests: PASS"
echo ""

# 2. Check git status
echo "[2/$TOTAL_STEPS] Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
    echo ""
    echo "FAIL: Uncommitted changes detected"
    echo ""
    git status --short
    echo ""
    echo "Commit or stash changes before signaling done."
    exit 1
fi
echo "Git status: CLEAN"
echo ""

# 3. Verify deliverables are tracked (if provided)
if [ $DELIVERABLE_COUNT -gt 0 ]; then
    echo "[3/$TOTAL_STEPS] Verifying deliverables are tracked in git..."
    for file in "$@"; do
        if ! git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
            echo ""
            echo "FAIL: $file is NOT tracked in git"
            echo ""
            echo "This file exists but was never committed."
            echo "Run: git add $file && git commit -m 'Add $file'"
            exit 1
        fi
        echo "  ✓ $file"
    done
    echo "Deliverables: $DELIVERABLE_COUNT file(s) TRACKED"
    echo ""
fi

echo "=== PASS: Ready to signal done ==="
exit 0
