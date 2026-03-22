---
name: sentinel-review
description: >-
  Generate a structured code review after completing a task. Reads session file
  operations from the change tracker, launches 7 specialist subagents in parallel,
  merges all findings into a JSON report, and opens it as a self-contained browser UI.
  Handles edits, creates, deletes, renames, and directory operations.
tools: Read, Write, Bash, Task, Glob, Grep
user-invocable: false
---

# Sentinel Review Skill

You are generating a structured code review of the task you just completed.
Follow every step in order. Do not skip steps. Do not abbreviate.

---

## Step 1 — Read session file operations

Read `.claude/reviews/tmp/session-timeline.json`.

If this file does not exist or contains an empty array `[]`, tell the user:
> "No file changes recorded for this session. Make some changes first, then run /sentinel-review."
And stop immediately — do not proceed.

From the timeline, build two structures:

**`file_operations`** — the full array of operation objects exactly as they appear in the timeline.
Each entry has at minimum: `time`, `operation`, and either `path` (for most operations) or `old_path`+`new_path` (for renames).

**`changed_files`** — a flat list of unique file paths that were touched:
- For `edit`, `create`, `delete`, `create_dir`, `delete_dir` → use `path`
- For `rename` → include BOTH `old_path` and `new_path`
- Deduplicate: each path appears only once

---

## Step 2 — Build conversation summary

Read the current conversation context and summarize the task:

```json
{
  "original_goal": "What the user asked for at the start of this conversation",
  "mid_task_pivots": ["Any direction change the user requested mid-task, with timing if known"],
  "final_intent": "What the task ultimately aimed to achieve",
  "approach_taken": "Brief description of how you solved it"
}
```

If the task was simple with no pivots, `mid_task_pivots` should be `[]`.
Be accurate — do not invent pivots that did not happen.

---

## Step 3 — Launch all 7 subagents in parallel

Use the Task tool to launch ALL 7 subagents simultaneously.
**CRITICAL: Do NOT wait for one to finish before launching the next.**
**Launch all 7 Task calls before awaiting any results.**

Use this exact prompt format for each subagent:

```
Analyze the following file operations and write your findings ONLY to
.claude/reviews/tmp/{AGENT_NAME}.json — write nothing else to disk.

File operations this session:
{JSON array of file_operations}

Changed files (flat list):
{JSON array of changed_files}

OUTPUT REQUIREMENTS:
- Write ONLY valid JSON to .claude/reviews/tmp/{AGENT_NAME}.json
- Create the .claude/reviews/tmp/ directory if it does not exist
- Every finding must include: level, found_by ("{AGENT_NAME}"), location, description, suggestion
- Include line numbers in every finding where possible
- Use level "UNCLEAR" for anything you cannot verify from the actual code — never fabricate
- DO NOT print anything to stdout — write ONLY to the JSON file

Follow your agent instructions exactly.
```

The 7 subagents to launch (all at once):

| Agent file | AGENT_NAME | Extra data |
|-----------|------------|------------|
| agents/master-reviewer.md | master-reviewer | Also pass: `Conversation summary: {JSON from Step 2}` |
| agents/security-auditor.md | security-auditor | file_operations + changed_files only |
| agents/regression-hunter.md | regression-hunter | file_operations + changed_files only |
| agents/performance-scout.md | performance-scout | file_operations + changed_files only |
| agents/code-usage-inspector.md | code-usage-inspector | file_operations + changed_files only |
| agents/test-critic.md | test-critic | file_operations + changed_files only |
| agents/code-quality-inspector.md | code-quality-inspector | file_operations + changed_files only |

---

## Step 4 — Write your own changes[] analysis (do this while subagents run)

While the 7 subagents are running, write your own analysis of each file operation.
For each entry in `file_operations`, produce one change object.

### EDIT operation
```json
{
  "operation": "edit",
  "file": "auth.js",
  "path": "src/middleware/auth.js",
  "old_path": null,
  "new_path": null,
  "lines": "14-67",
  "risk": "HIGH",
  "confidence": "HIGH",
  "why": "Plain English — why was this file changed",
  "behavior_before": "Plain English — what the code did before this change",
  "behavior_after": "Plain English — what the code does now",
  "diff": "--- a/src/middleware/auth.js\n+++ b/src/middleware/auth.js\n@@ -14,5 +14,9 @@\n...",
  "note": null,
  "files_added": null,
  "files_deleted": null,
  "potential_issues": ["String describing a potential issue"],
  "ripple_effects": ["String describing ripple effect"],
  "alternatives": [{ "name": "Alternative name", "pros": ["..."], "cons": ["..."] }],
  "fix_flow": { "is_fix": false, "bug_description": null, "reproduce_steps": [], "verify_steps": [], "edge_cases_to_test": [] }
}
```
**Diff generation for edits:**
1. First try: `git diff HEAD -- {path}` — gives unified diff with context
2. If that fails: `git show HEAD:{path}` to get pre-edit version, then format manually
3. If no git: set `diff: null` and `note: "No git history available — diff could not be generated"`

### CREATE operation (new file)
```json
{
  "operation": "create",
  "file": "tokenHelper.js",
  "path": "src/utils/tokenHelper.js",
  "old_path": null,
  "new_path": null,
  "lines": "1-45",
  "risk": "MED",
  "confidence": "HIGH",
  "why": "Why was this new file created",
  "behavior_before": null,
  "behavior_after": "What this new file provides",
  "diff": "--- /dev/null\n+++ b/src/utils/tokenHelper.js\n@@ -0,0 +1,12 @@\n+const formatToken = ...",
  "note": "New file — entire content shown as additions",
  "files_added": null,
  "files_deleted": null,
  "potential_issues": ["..."],
  "ripple_effects": ["Any file that now imports this"],
  "alternatives": [],
  "fix_flow": { "is_fix": false, "bug_description": null, "reproduce_steps": [], "verify_steps": [], "edge_cases_to_test": [] }
}
```
**`behavior_before` MUST be null for create operations.**
Diff format: `--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{N} @@\n+line1\n+line2...`
For files >200 lines: include first 50 and last 20 lines, with `note: "File truncated — showing first 50 and last 20 lines"`.

### DELETE operation (removed file)
```json
{
  "operation": "delete",
  "file": "legacyAuth.js",
  "path": "src/middleware/legacyAuth.js",
  "old_path": null,
  "new_path": null,
  "lines": "1-112",
  "risk": "HIGH",
  "confidence": "MED",
  "why": "Why was this file deleted",
  "behavior_before": "What this file provided before deletion",
  "behavior_after": null,
  "diff": "--- a/src/middleware/legacyAuth.js\n+++ /dev/null\n@@ -1,8 +0,0 @@\n-const legacyCheck...",
  "note": "File deleted — entire content shown as removals",
  "files_added": null,
  "files_deleted": null,
  "potential_issues": [
    "Any code still importing this file will fail at runtime",
    "Verify replacement functionality exists"
  ],
  "ripple_effects": ["Search for all imports of this file"],
  "alternatives": [],
  "fix_flow": { "is_fix": false, "bug_description": null, "reproduce_steps": [], "verify_steps": [], "edge_cases_to_test": [] }
}
```
**`behavior_after` MUST be null for delete operations.**
**Risk defaults to HIGH for all deletes** — lower only if confirmed no callers exist.
Get deleted file content via `git show HEAD:{path}` before generating diff.

### RENAME operation (moved/renamed file)
```json
{
  "operation": "rename",
  "file": null,
  "path": null,
  "old_path": "src/auth/checkToken.js",
  "new_path": "src/middleware/tokenValidator.js",
  "lines": null,
  "risk": "HIGH",
  "confidence": "HIGH",
  "why": "Why was this file renamed or moved",
  "behavior_before": "Was imported from old_path",
  "behavior_after": "Must now be imported from new_path",
  "diff": null,
  "note": "File renamed/moved — content unchanged. All importers of old path must be updated.",
  "files_added": null,
  "files_deleted": null,
  "potential_issues": [
    "All files importing from old path will fail until updated",
    "Build tool aliases (webpack, tsconfig, jest) may reference old path"
  ],
  "ripple_effects": ["Search entire codebase for imports of old path"],
  "alternatives": [],
  "fix_flow": { "is_fix": false, "bug_description": null, "reproduce_steps": [], "verify_steps": [], "edge_cases_to_test": [] }
}
```
**`diff` MUST be null for rename operations.**

### CREATE_DIR operation
```json
{
  "operation": "create_dir",
  "file": null,
  "path": "src/utils/auth/",
  "old_path": null,
  "new_path": null,
  "lines": null,
  "risk": "LOW",
  "confidence": "HIGH",
  "why": "Why was this directory created",
  "behavior_before": null,
  "behavior_after": "New directory for organizing files",
  "diff": null,
  "note": "Directory created — no diff",
  "files_added": ["src/utils/auth/tokenHelper.js", "src/utils/auth/sessionHelper.js"],
  "files_deleted": null,
  "potential_issues": [],
  "ripple_effects": [],
  "alternatives": [],
  "fix_flow": { "is_fix": false, "bug_description": null, "reproduce_steps": [], "verify_steps": [], "edge_cases_to_test": [] }
}
```
**`behavior_before` MUST be null. `diff` MUST be null.**

### DELETE_DIR operation
```json
{
  "operation": "delete_dir",
  "file": null,
  "path": "src/legacy/",
  "old_path": null,
  "new_path": null,
  "lines": null,
  "risk": "HIGH",
  "confidence": "MED",
  "why": "Why was this directory removed",
  "behavior_before": "Contained legacy authentication modules",
  "behavior_after": null,
  "diff": null,
  "note": "Directory and all contents deleted",
  "files_added": null,
  "files_deleted": ["src/legacy/auth.js", "src/legacy/session.js"],
  "potential_issues": ["All imports of files in this directory will break"],
  "ripple_effects": ["Search for imports of all deleted files"],
  "alternatives": [],
  "fix_flow": { "is_fix": false, "bug_description": null, "reproduce_steps": [], "verify_steps": [], "edge_cases_to_test": [] }
}
```
**`behavior_after` MUST be null. `diff` MUST be null.**

### Fix flow (for bug-fix tasks)
If the change IS a bug fix, set `fix_flow.is_fix: true` and fill in:
```json
{
  "is_fix": true,
  "bug_description": "What the bug was",
  "reproduce_steps": ["Step 1", "Step 2"],
  "verify_steps": ["Step to verify the fix works"],
  "edge_cases_to_test": ["Edge case that might still be broken"]
}
```

---

## Step 5 — Wait for all 7 subagents to complete

Do not write the final JSON until all subagents have completed.
Check for these files:
- `.claude/reviews/tmp/master-reviewer.json`
- `.claude/reviews/tmp/security-auditor.json`
- `.claude/reviews/tmp/regression-hunter.json`
- `.claude/reviews/tmp/performance-scout.json`
- `.claude/reviews/tmp/code-usage-inspector.json`
- `.claude/reviews/tmp/test-critic.json`
- `.claude/reviews/tmp/code-quality-inspector.json`

If any file is missing after all Task calls complete, note the missing agent and continue
with the agents that did complete. Do not fail the entire review for one missing agent.

---

## Step 6 — Merge all subagent findings

Read all available tmp files. Then:

**Merge findings:**
1. Collect every `findings[]` entry from all files → one flat array
2. Sort by severity: CRITICAL → HIGH → MED → LOW → DISCUSS → UNCLEAR
3. Deduplicate: if two findings share the same `location` AND the same issue type,
   keep the higher severity one, add `"also_found_by": ["other-agent-name"]`
4. Every finding must have `found_by` set to the exact agent name string

**Merge next_steps:**
1. Collect all `next_steps[]` entries from all files → one flat array
2. Remove exact duplicates (same action text)
3. Sort by priority: CRITICAL → HIGH → MED → LOW

**Collect suggested_tests:**
1. Collect all `suggested_tests[]` from test-critic only → one flat array
2. If test-critic file is missing, use `[]`

**Extract from master-reviewer:**
- `intent_vs_reality` object
- `session_timeline` array
If master-reviewer file is missing, use these defaults:
- `intent_vs_reality`: reconstruct from your own conversation summary
- `session_timeline`: reconstruct from file_operations timestamps

---

## Step 7 — Generate task slug

Create a URL-safe slug from the task description:
- Lowercase only
- Replace spaces and special characters with hyphens
- Maximum 40 characters
- Example: "Refactor Auth Middleware" → `refactor-auth-middleware`

---

## Step 8 — Write the final review JSON

**Path:** `.claude/reviews/YYYY-MM-DD-{task-slug}.json`
(Use today's actual date in YYYY-MM-DD format.)

The JSON must have EXACTLY these top-level keys in this order:
`meta`, `intent_vs_reality`, `session_timeline`, `changes`, `findings`, `suggested_tests`, `next_steps`

**All keys must be present.** Fields that are N/A for the current mode use `null` or `[]`, never omission.

```json
{
  "meta": {
    "task": "Human-readable description of what the task did",
    "date": "YYYY-MM-DD",
    "session_id": "YYYYMMDD-HHMMSS",
    "mode": "review",
    "files_changed": 4,
    "overall_risk": "CRITICAL|HIGH|MED|LOW"
  },
  "intent_vs_reality": {
    "original_goal": "...",
    "mid_task_pivots": [],
    "final_intent": "...",
    "completed": ["..."],
    "extra": ["..."],
    "missing": ["..."]
  },
  "session_timeline": [
    { "time": "HH:MM", "event": "Human-readable description" }
  ],
  "changes": [ ... ],
  "findings": [
    {
      "level": "CRITICAL|HIGH|MED|LOW|DISCUSS|UNCLEAR",
      "found_by": "agent-name",
      "also_found_by": [],
      "location": "src/routes/api.js",
      "line": 34,
      "description": "Clear description of the issue",
      "suggestion": "Specific actionable fix"
    }
  ],
  "suggested_tests": [
    {
      "file": "tests/auth.test.js",
      "description": "should return 401 when token is expired",
      "why_valuable": "Token expiry is a security boundary"
    }
  ],
  "next_steps": [
    {
      "priority": "CRITICAL|HIGH|MED|LOW",
      "action": "Specific action to take",
      "found_by": "agent-name",
      "location": "file:line if applicable"
    }
  ]
}
```

**overall_risk calculation:** Set to the highest severity level found across all findings.
If findings include any CRITICAL → `"CRITICAL"`. Else if any HIGH → `"HIGH"`. Etc.
If no findings at all → `"LOW"`.

**Validate** the JSON is syntactically correct before writing. If invalid, fix it.

---

## Step 9 — Clean up

Delete the entire `.claude/reviews/tmp/` directory:
```bash
rm -rf .claude/reviews/tmp
```
On Windows Git Bash this command works. Alternatively: `python -c "import shutil; shutil.rmtree('.claude/reviews/tmp', ignore_errors=True)"`

---

## Step 10 — Open the UI

Determine the plugin root path. The plugin root is the directory containing `skills/`, `agents/`, `scripts/`, etc.
Run:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/open_review.py" ".claude/reviews/{FILENAME}.json"
```

If `CLAUDE_PLUGIN_ROOT` is not set, derive it by finding the `sentinel-plugin` directory.

Tell the user:
> "✅ Review complete. Opening in browser."

---

## Null Rules Summary (CRITICAL — never violate these)

| Field | null for these operations |
|-------|--------------------------|
| `behavior_before` | `create`, `create_dir` |
| `behavior_after` | `delete`, `delete_dir` |
| `diff` | `rename`, `create_dir`, `delete_dir` |
| `old_path`, `new_path` | all operations except `rename` |
| `files_added` | all operations except `create_dir` |
| `files_deleted` | all operations except `delete_dir` |

Fields set to null must still be PRESENT in the JSON object — never omit them entirely.
This keeps UI rendering simple: `if (change.behavior_before !== null)`.
