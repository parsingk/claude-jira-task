#!/usr/bin/env bash
# claude-jira-task — Python launcher wrapper
# Picks `python3` if available, else `python`. Graceful degradation if neither found.
# Works on Linux, macOS, and Windows (via Git Bash).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/pretooluse_jira_check.py"

if command -v python3 >/dev/null 2>&1; then
    exec python3 "$PY_SCRIPT"
elif command -v python >/dev/null 2>&1; then
    exec python "$PY_SCRIPT"
else
    # Python not found — log a warning but DO NOT block the commit.
    # User can still work; they'll see the warning and install Python at their convenience.
    echo "[claude-jira-task] warning: Python 3 not found (neither 'python3' nor 'python' on PATH). Skipping Jira task check. Install Python 3 and restart Claude Code to enable hook." >&2
    exit 0
fi
