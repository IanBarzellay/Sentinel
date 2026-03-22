#!/usr/bin/env python3
"""
Sentinel PostToolUse hook handler.
Called by Claude Code after every Write, Edit, MultiEdit, and Bash tool use.
Appends file operation entries to the session timeline JSON.

Environment variables set by Claude Code:
  CLAUDE_TOOL_NAME  - name of the tool that just ran (Write, Edit, MultiEdit, Bash)
  TOOL_INPUT        - JSON string of the tool's input parameters
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime


# Timeline is always relative to the current working directory (the user's project)
TIMELINE_FILE = Path(".claude") / "reviews" / "tmp" / "session-timeline.json"


def main():
    tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
    tool_input_raw = os.environ.get("TOOL_INPUT", "{}")

    # Parse tool input
    try:
        tool_input = json.loads(tool_input_raw)
    except (json.JSONDecodeError, ValueError):
        return  # Invalid JSON — skip silently

    # Classify the operation
    entry = classify_operation(tool_name, tool_input)
    if entry is None:
        return  # Not a file operation — skip

    # Ensure the tmp directory exists
    try:
        TIMELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return  # Cannot create directory — skip silently

    # Read existing timeline
    timeline = []
    if TIMELINE_FILE.exists():
        try:
            content = TIMELINE_FILE.read_text(encoding="utf-8")
            timeline = json.loads(content)
            if not isinstance(timeline, list):
                timeline = []
        except (json.JSONDecodeError, OSError):
            timeline = []

    # Resolve create vs edit for Write operations
    if entry.get("_needs_create_check"):
        path = entry.get("path", "")
        # First time this path appears in the timeline = create, subsequent = edit
        already_seen = any(
            e.get("path") == path or e.get("new_path") == path
            for e in timeline
        )
        entry["operation"] = "edit" if already_seen else "create"
        del entry["_needs_create_check"]

    # Add timestamp
    entry["time"] = datetime.now().strftime("%H:%M:%S")

    # Append to timeline
    timeline.append(entry)

    # Write back
    try:
        TIMELINE_FILE.write_text(
            json.dumps(timeline, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except OSError:
        pass  # Cannot write — skip silently


def classify_operation(tool_name, tool_input):
    """Return a timeline entry dict for the given tool use, or None if not a file op."""

    if tool_name == "Edit":
        path = tool_input.get("file_path") or tool_input.get("path", "")
        if not path:
            return None
        return {"operation": "edit", "path": normalize_path(path)}

    elif tool_name == "MultiEdit":
        # MultiEdit has file_path at top level
        path = tool_input.get("file_path") or tool_input.get("path", "")
        if not path:
            return None
        return {"operation": "edit", "path": normalize_path(path)}

    elif tool_name == "Write":
        path = tool_input.get("file_path") or tool_input.get("path", "")
        if not path:
            return None
        return {
            "operation": "create",  # will be resolved to edit if seen before
            "path": normalize_path(path),
            "_needs_create_check": True
        }

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        return classify_bash_command(command)

    return None  # Other tool types — not a file operation


def classify_bash_command(cmd):
    """Classify a bash command as a file operation, or return None."""
    if not cmd or not cmd.strip():
        return None

    # Strip comments
    cmd = cmd.split("#")[0].strip()

    # Check for rm (delete) — check recursive first
    if re.search(r"\brm\b", cmd):
        if re.search(r"\brm\b\s+(?:[^\s]*\s+)*-[^-]*[rR]", cmd) or \
           re.search(r"\brm\b\s+-[rR]", cmd) or \
           re.search(r"-rf\b|-fr\b|-Rf\b|-fR\b", cmd):
            path = extract_path_after_rm(cmd)
            if path:
                return {"operation": "delete_dir", "path": path}
        else:
            path = extract_path_after_rm(cmd)
            if path:
                return {"operation": "delete", "path": path}

    # Check for unlink (delete)
    if re.search(r"\bunlink\b", cmd):
        path = extract_path_after_keyword(cmd, "unlink")
        if path:
            return {"operation": "delete", "path": path}

    # Check for mkdir (create directory)
    if re.search(r"\bmkdir\b", cmd):
        path = extract_mkdir_path(cmd)
        if path:
            return {"operation": "create_dir", "path": path}

    # Check for mv (rename/move)
    if re.search(r"\bmv\b", cmd):
        paths = extract_mv_paths(cmd)
        if paths:
            return {
                "operation": "rename",
                "old_path": paths[0],
                "new_path": paths[1]
            }

    return None  # Non-file bash command


def extract_path_after_rm(cmd):
    """Extract the target path from an rm command."""
    # Match rm with optional flags, capture the path argument
    # Handles: rm file.js, rm -rf dir/, rm -f file.js, rm -- file.js
    m = re.search(r"\brm\b\s+(?:-\S+\s+)*(?:--\s+)?([^\s;|&<>]+)", cmd)
    if m:
        path = m.group(1).strip("\"'")
        # Skip if it looks like a flag
        if not path.startswith("-"):
            return normalize_path(path)
    return ""


def extract_path_after_keyword(cmd, keyword):
    """Extract path after a keyword like 'unlink'."""
    m = re.search(rf"\b{keyword}\b\s+([^\s;|&<>]+)", cmd)
    if m:
        return normalize_path(m.group(1).strip("\"'"))
    return ""


def extract_mkdir_path(cmd):
    """Extract the target path from a mkdir command."""
    # Match mkdir with optional -p flag
    m = re.search(r"\bmkdir\b\s+(?:-p\s+)?([^\s;|&<>]+)", cmd)
    if m:
        return normalize_path(m.group(1).strip("\"'"))
    return ""


def extract_mv_paths(cmd):
    """Extract (old_path, new_path) from an mv command."""
    # Remove 'mv' and any flags, then split remaining args
    remainder = re.sub(r"^.*?\bmv\b\s+", "", cmd).strip()
    # Remove flags like -f, -n, -u, -v, --
    remainder = re.sub(r"(?:^|\s)-\w+\b", " ", remainder).strip()
    remainder = re.sub(r"^--\s+", "", remainder).strip()

    # Split into tokens (handle quoted paths)
    tokens = re.findall(r'"[^"]*"|\'[^\']*\'|\S+', remainder)
    tokens = [t.strip("\"'") for t in tokens]

    if len(tokens) >= 2:
        return (normalize_path(tokens[-2]), normalize_path(tokens[-1]))
    return None


def normalize_path(path):
    """Normalize path separators to forward slashes."""
    return path.replace("\\", "/").strip()


if __name__ == "__main__":
    main()
