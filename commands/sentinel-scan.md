---
description: >-
  Deep scan the entire repository for security vulnerabilities, performance issues,
  duplicate/misused code, and quality problems.
  Usage: /sentinel-scan [security|performance|usage|quality|all]
  Omit argument (or use "all") to run all four scanners.
---

# Sentinel Scan Command

## Step 1 — Parse scope argument

Read `$ARGUMENTS` to determine which scanners to run:
- `"security"` → security-auditor only
- `"performance"` → performance-scout only
- `"usage"` → code-usage-inspector only
- `"quality"` → code-quality-inspector only
- `""` or `"all"` → all four scanners

Tell the user which scope is being used before starting.

## Step 2 — Discover all source files

Use Glob to find all relevant source files in the repository.

Exclude these patterns:
- `**/node_modules/**`
- `**/.git/**`
- `**/dist/**`
- `**/build/**`
- `**/coverage/**`
- `**/.claude/**`
- `**/*.min.js`
- `**/*.min.css`
- `**/*.lock`
- `**/*.map`
- `**/vendor/**`

Build `repo_files` — a flat list of all relevant source file paths.

Tell the user: `"Scanning {N} files with: {scanner names}..."`

## Step 3 — Launch scanners in parallel

For each scanner in scope, launch a Task with this prompt:

```
Perform a FULL REPOSITORY SCAN — this is NOT a task review.
Scan the ENTIRE repository for existing issues.

All source files to scan:
{JSON array of repo_files}

Write findings ONLY to .claude/reviews/tmp/{AGENT_NAME}.json
Create the directory if it does not exist.

Output schema:
{
  "agent": "{AGENT_NAME}",
  "scope": "full_repo",
  "findings": [
    {
      "level": "CRITICAL|HIGH|MED|LOW|DISCUSS|UNCLEAR",
      "found_by": "{AGENT_NAME}",
      "also_found_by": [],
      "location": "path/to/file.js",
      "line": null,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "next_steps": [
    {
      "priority": "CRITICAL|HIGH|MED|LOW",
      "action": "...",
      "found_by": "{AGENT_NAME}",
      "location": "file:line"
    }
  ]
}

Every finding must cite a specific file path. Include line numbers where possible.
Use UNCLEAR for anything you cannot verify from the actual code.
DO NOT print anything to stdout — write ONLY to the JSON file.

Follow your agent instructions exactly.
```

Launch all applicable scanners simultaneously — do NOT wait for one before starting another.

## Step 4 — Wait for all scanners to complete

Wait for all launched Task calls to finish.

## Step 5 — Merge findings

Read all available `.claude/reviews/tmp/{agent-name}.json` files.

1. Collect all `findings[]` → one flat array
2. Sort by severity: CRITICAL → HIGH → MED → LOW → DISCUSS → UNCLEAR
3. Deduplicate: same location + same issue → keep higher severity, add `also_found_by`
4. Merge all `next_steps[]` → deduplicate by action text → sort by priority

## Step 6 — Write scan report

**Path:** `.claude/reviews/YYYY-MM-DD-scan-{scope}.json`

```json
{
  "meta": {
    "task": "Repository scan — {scope}",
    "date": "YYYY-MM-DD",
    "session_id": "YYYYMMDD-HHMMSS",
    "mode": "scan",
    "scope": "full_repo",
    "scanners_run": ["security-auditor", "..."],
    "files_scanned": 142,
    "overall_risk": "HIGH"
  },
  "findings": [...],
  "next_steps": [...]
}
```

Note: scan mode does NOT include `intent_vs_reality`, `session_timeline`, `changes`, or `suggested_tests`.
These fields are omitted entirely in scan mode (not set to null — simply absent).

## Step 7 — Clean up and open UI

Delete `.claude/reviews/tmp/` directory.

Run:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/open_review.py" ".claude/reviews/{FILENAME}.json"
```

Tell the user:
> "✅ Scan complete. {N} findings across {M} files. Opening in browser."
