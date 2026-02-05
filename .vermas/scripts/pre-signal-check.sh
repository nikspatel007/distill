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

# Parse flags
ALLOW_NO_DELIVERABLES=false
DELIVERABLES=()

for arg in "$@"; do
    if [ "$arg" = "--allow-no-deliverables" ]; then
        ALLOW_NO_DELIVERABLES=true
    else
        DELIVERABLES+=("$arg")
    fi
done

DELIVERABLE_COUNT=${#DELIVERABLES[@]}

# Fail-safe: require deliverables unless explicitly opted out
if [ $DELIVERABLE_COUNT -eq 0 ] && [ "$ALLOW_NO_DELIVERABLES" = false ]; then
    echo "ERROR: No deliverables specified."
    echo ""
    echo "Every task should have deliverables to verify. This prevents"
    echo "signaling 'done' when code exists but was never committed."
    echo ""
    echo "Usage: pre-signal-check.sh <deliverable1> [deliverable2] ..."
    echo "       pre-signal-check.sh --allow-no-deliverables  # For docs-only changes"
    echo ""
    echo "Examples:"
    echo "  pre-signal-check.sh src/module.py tests/test_module.py"
    echo "  pre-signal-check.sh --allow-no-deliverables  # Only if no code changes"
    exit 1
fi

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
    for file in "${DELIVERABLES[@]}"; do
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
