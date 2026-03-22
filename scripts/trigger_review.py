#!/usr/bin/env python3
"""
Sentinel Stop hook handler.
Called by Claude Code when a task completes (Stop hook).
Reads the session timeline and either:
  (A) Auto-triggers review via Claude CLI (if available), or
  (B) Prints a visible terminal reminder to run /sentinel-review
"""

import os
import sys
import json
import subprocess
from pathlib import Path


# Timeline is relative to the current working directory (the user's project)
TIMELINE_FILE = Path(".claude") / "reviews" / "tmp" / "session-timeline.json"

# Operations that count as "meaningful" file changes worth reviewing
MEANINGFUL_OPERATIONS = {"edit", "create", "delete", "rename"}


def main():
    # Exit quietly if no timeline exists (task had no file operations)
    if not TIMELINE_FILE.exists():
        return

    # Read timeline
    try:
        content = TIMELINE_FILE.read_text(encoding="utf-8")
        timeline = json.loads(content)
        if not isinstance(timeline, list):
            return
    except (json.JSONDecodeError, OSError):
        return

    # Count meaningful file operations
    meaningful = [
        entry for entry in timeline
        if entry.get("operation") in MEANINGFUL_OPERATIONS
    ]
    count = len(meaningful)

    if count == 0:
        return  # Only directory ops or nothing — skip notification

    # ── Option A: Attempt CLI auto-invocation ────────────────────────────────
    # If Claude Code CLI is available and accessible, attempt to auto-run the review.
    # This makes the review fully automatic (user doesn't need to type /sentinel-review).
    # If it fails for any reason, fall through to the manual prompt.
    if _try_cli_invocation():
        return  # Auto-triggered successfully

    # ── Option B: Print visible terminal reminder ─────────────────────────────
    _print_reminder(count)


def _try_cli_invocation():
    """
    Attempt to invoke the Claude Code CLI to auto-run the sentinel-review skill.
    Returns True if invocation appeared to succeed, False otherwise.
    """
    try:
        result = subprocess.run(
            ["claude", "--print", "Run the sentinel-review skill to generate a code review."],
            capture_output=True,
            timeout=15,
            text=True
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _print_reminder(count):
    """Print a visible banner to the terminal."""
    file_word = "file operation" if count == 1 else "file operations"

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  ✅  Task complete — {count} {file_word} recorded")
    print("║  Type  /sentinel-review  to generate your code review        ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    main()
