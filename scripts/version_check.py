#!/usr/bin/env python3
"""
claude-jira-task plugin — version check helper

Best-effort check that prints a one-line notice to stdout when a newer plugin
version is available on the marketplace source repository. Otherwise prints
nothing. Always exits 0. Result is cached for 24h.

Strategy
--------
- Local version: highest version directory under
  ~/.claude/plugins/cache/<marketplace>/claude-jira-task/.
- Remote version: read .claude-plugin/plugin.json from origin/main of the
  marketplace source repo at ~/.claude/plugins/marketplaces/<marketplace>/
  after `git fetch origin`. Identified by manifest.name == "claude-jira-task".
- Compare with a lightweight SemVer-ish key; if remote > local, print notice.

Designed to run on Linux / macOS / Windows (Git Bash).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path


PLUGIN_NAME = "claude-jira-task"
CACHE_TTL_SECONDS = 24 * 60 * 60


def _semver_key(version: str) -> tuple:
    parts = re.split(r"[.\-+]", version)
    out: list[tuple[int, object]] = []
    for p in parts:
        out.append((0, int(p)) if p.isdigit() else (1, p))
    return tuple(out)


def _find_marketplace_dir() -> Path | None:
    root = Path.home() / ".claude" / "plugins" / "marketplaces"
    if not root.is_dir():
        return None
    for entry in root.iterdir():
        manifest = entry / ".claude-plugin" / "plugin.json"
        if not (entry / ".git").is_dir() or not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("name") == PLUGIN_NAME:
            return entry
    return None


def _find_local_version() -> str | None:
    cache_root = Path.home() / ".claude" / "plugins" / "cache"
    if not cache_root.is_dir():
        return None
    versions: list[str] = []
    for marketplace_dir in cache_root.iterdir():
        plugin_dir = marketplace_dir / PLUGIN_NAME
        if not plugin_dir.is_dir():
            continue
        for v_dir in plugin_dir.iterdir():
            if v_dir.is_dir() and not v_dir.name.startswith("."):
                versions.append(v_dir.name)
    if not versions:
        return None
    return sorted(versions, key=_semver_key)[-1]


def _fetch_remote_version(marketplace_dir: Path) -> str | None:
    try:
        subprocess.run(
            ["git", "-C", str(marketplace_dir), "fetch", "origin", "--quiet"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        result = subprocess.run(
            ["git", "-C", str(marketplace_dir), "show", "origin/main:.claude-plugin/plugin.json"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return json.loads(result.stdout.decode("utf-8", errors="replace")).get("version")
    except Exception:
        return None


def _cache_path() -> Path:
    return Path.home() / ".cache" / "claude-jira-task" / "version-check.json"


def _read_cached_remote(local_version: str) -> str | None:
    path = _cache_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("local") != local_version:
        return None
    if time.time() - data.get("cached_at", 0) > CACHE_TTL_SECONDS:
        return None
    return data.get("remote")


def _write_cache(local_version: str, remote_version: str) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"cached_at": int(time.time()), "local": local_version, "remote": remote_version}
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def main() -> None:
    local = _find_local_version()
    if not local:
        return

    remote = _read_cached_remote(local)
    if remote is None:
        marketplace_dir = _find_marketplace_dir()
        if marketplace_dir is None:
            return
        remote = _fetch_remote_version(marketplace_dir)
        if not remote:
            return
        _write_cache(local, remote)

    if remote != local and _semver_key(remote) > _semver_key(local):
        notice = f"📦 claude-jira-task v{remote} 사용 가능 (현재 v{local})\n"
        # Write UTF-8 bytes directly so Windows cp949 / Korean locale consoles
        # don't raise UnicodeEncodeError on the emoji or Hangul.
        sys.stdout.buffer.write(notice.encode("utf-8"))
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
