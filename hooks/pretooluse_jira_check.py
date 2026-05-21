#!/usr/bin/env python3
"""
claude-jira-task plugin — PreToolUse hook

Blocks `git commit` invocations when there is no active Jira task whose key
appears in the current branch name. Activates only for repos that have opted
in by creating `.claude/jira-config.json` (the file the plugin writes at first
`/jira-task` invocation).

Behavior:
- Reads tool-call payload from stdin (JSON).
- Inspects only Bash tool calls whose command starts with / contains `git commit`.
- Finds the repo root via `git rev-parse --show-toplevel`.
- If `<repo>/.claude/jira-config.json` does not exist, allows (repo not opted in).
- If `<repo>/.claude/active-jira-tasks.json` lists a task whose `key` is a substring
  of the current branch name (`git branch --show-current`), allows.
- Otherwise denies with a message instructing the user to run `/jira-task`.

Exit codes:
- 0 → allow tool call to proceed
- 2 → block tool call (Claude Code shows stderr message back to Claude)

Designed to be cross-platform (Linux / macOS / Windows via Git Bash).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def run_git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main() -> None:
    # Read hook payload from stdin
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # malformed input — allow

    tool_name = payload.get("tool_name") or payload.get("toolName") or ""
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}

    # Only inspect Bash tool calls
    if tool_name != "Bash":
        sys.exit(0)

    cmd = (tool_input.get("command") or "").strip()
    # Match `git commit` (with or without flags), not `git commit-tree` etc.
    # The pattern allows `git`, optional flags between, then `commit` as a separate word
    # not followed by an alpha character or `-` (which would make it `commit-tree`).
    if not re.search(r"\bgit\b(?:\s+--?\S+)*\s+commit\b(?!-)", cmd):
        sys.exit(0)

    # Determine cwd
    cwd_str = payload.get("cwd") or payload.get("working_directory")
    cwd = Path(cwd_str) if cwd_str else Path.cwd()

    # Find git repo root
    repo_root_str = run_git(["rev-parse", "--show-toplevel"], cwd)
    if not repo_root_str:
        sys.exit(0)  # not a git repo — allow
    repo_root = Path(repo_root_str)

    # Opt-in check: this repo must have .claude/jira-config.json
    jira_config_path = repo_root / ".claude" / "jira-config.json"
    if not jira_config_path.exists():
        sys.exit(0)

    # Get current branch
    branch = run_git(["branch", "--show-current"], cwd) or ""

    # Read active tasks
    active_tasks_path = repo_root / ".claude" / "active-jira-tasks.json"
    active_keys: list[str] = []
    if active_tasks_path.exists():
        try:
            data = json.loads(active_tasks_path.read_text(encoding="utf-8"))
            for t in data.get("tasks", []):
                key = t.get("key")
                if key:
                    active_keys.append(key)
        except Exception:
            pass  # treat as no active tasks

    # Check branch contains any active task key
    for key in active_keys:
        if key and key in branch:
            sys.exit(0)  # match — allow

    # No match → block
    msg = (
        "[claude-jira-task] 커밋을 차단했습니다.\n"
        f"  현재 브랜치: {branch or '(unknown)'}\n"
        f"  활성 task 키: {', '.join(active_keys) if active_keys else '(없음)'}\n\n"
        "이 브랜치에 매칭되는 활성 Jira task 가 없습니다. `/jira-task` 로 먼저 등록한 뒤\n"
        "등록 절차에서 선택한 격리 방식(별도 worktree 또는 현재 디렉토리)대로\n"
        "생성된 새 브랜치에서 커밋해 주세요.\n\n"
        "(이 검사는 .claude/jira-config.json 이 있는 repo 에만 적용됩니다.\n"
        " 이 repo 에서 워크플로를 끄려면 `/jira-task config reset` 또는 그 파일 삭제.)"
    )
    sys.stderr.write(msg + "\n")
    sys.exit(2)


if __name__ == "__main__":
    main()
