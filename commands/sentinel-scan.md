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
      "suggestion": "...",
      "current_code": {
        "start_line": 10,
        "content": "// context line\nbad code here;\n// context line",
        "highlight_start": 2,
        "highlight_end": 2
      },
      "suggested_code": {
        "content": "// context line\nfixed code here;\n// context line",
        "highlight_start": 2,
        "highlight_end": 2
      }
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

**current_code / suggested_code rules:**
- These fields are OPTIONAL — include them only when the finding points to a specific line or block that should change
- Use the Read tool with `offset` and `limit` to fetch the exact lines from the file
- Include 2–3 context lines before and after the changed line(s)
- `highlight_start` / `highlight_end` are 1-indexed within the `content` string (not absolute file line numbers)
- `suggested_code` has no `start_line` — its line numbers mirror `current_code`
- If the finding is conceptual (missing pattern, architectural concern, no specific fix line) — omit both fields entirely
- Never fabricate code — only include lines you actually read from the file

Follow your agent instructions exactly.
```

Launch all applicable scanners simultaneously — do NOT wait for one before starting another.

## Step 4 — Wait for all scanners to complete

Wait for all launched Task calls to finish.

## Step 5 — Validate outputs and retry if needed

For each scanner that was run, execute the validator:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/validate_agent_output.py" ".claude/reviews/tmp/{AGENT_NAME}.json"
```

Parse each JSON report from stdout. Collect all scanners where **either**:
- `can_proceed: false` (file-level failure), **or**
- `finding_issues` contains any entry with a non-empty `critical` array

### Retry loop (max 2 rounds)

If any scanners need a retry, launch Tasks for all of them **in parallel**:

```
Your previous output at .claude/reviews/tmp/{AGENT_NAME}.json had these issues:

File-level errors:
{critical_errors from validation report — one per line}

Per-finding issues:
{for each entry in finding_issues where critical is non-empty:
  Finding #{index + 1}: {critical list joined by ", "}
}

Re-scan the relevant files and rewrite ONLY the problematic findings with
corrected data. Overwrite the same file completely.
Follow your original agent instructions exactly for output format.
```

Wait for all retry Tasks to complete.
Re-run the validator on each retried scanner's file.
If any still fail, repeat **once more** (2 retries total per scanner maximum).

### After max retries

For each scanner, regardless of remaining issues:
- `valid_findings > 0` → use only the valid findings in Step 6 (skip invalid ones by index)
- `valid_findings == 0` and `total_findings > 0` → skip this scanner's output entirely
- `total_findings == 0` → scanner found no issues — valid result, proceed normally

## Step 6 — Merge findings

Read all available `.claude/reviews/tmp/{agent-name}.json` files.

1. Collect all `findings[]` → one flat array
2. Sort by severity: CRITICAL → HIGH → MED → LOW → DISCUSS → UNCLEAR
3. Deduplicate: same location + same issue → keep higher severity, add `also_found_by`
4. Merge all `next_steps[]` → deduplicate by action text → sort by priority

## Step 7 — Write scan report

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

## Step 8 — Clean up and open UI

Delete `.claude/reviews/tmp/` directory.

Run:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/open_review.py" ".claude/reviews/{FILENAME}.json"
```

Tell the user:
> "✅ Scan complete. {N} findings across {M} files. Opening in browser."
