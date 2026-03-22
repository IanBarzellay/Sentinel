# 🛡️ Sentinel — Code Review Plugin for Claude Code

Sentinel puts a genuine peer-review layer between "Claude finished the task" and "you ship the code." It silently tracks every file change during a task, then on demand launches 7 specialist subagents in parallel to produce a structured, risk-scored review — opened instantly as a self-contained browser UI.

---

## What it does

| Feature | Description |
|---------|-------------|
| **Change tracking** | Automatically records every file edit, create, delete, rename, and directory operation during a task |
| **7 specialist subagents** | Master Reviewer, Security Auditor, Regression Hunter, Performance Scout, Code Usage Inspector, Test Critic, Code Quality Inspector — all run in parallel |
| **Risk scoring** | Every finding rated CRITICAL / HIGH / MED / LOW / DISCUSS / UNCLEAR |
| **Browser UI** | Self-contained HTML report with dark mode, live search, severity filters, agent filters, diff viewer, and keyboard shortcuts |
| **Repo scan mode** | `/sentinel-scan` for proactive full-repo audits — no task context needed |
| **Offline-first** | HTML reports work without internet (diff2html is downloaded once and cached) |

---

## Requirements

- **Claude Code** (the CLI tool that runs this plugin)
- **Python ≥ 3.8** (for change tracking scripts and browser opener)
- **Node.js ≥ 18** (for HTML report generation)
- **Git** (recommended — enables diff generation for change cards)

---

## Installation

Point Claude Code at the `sentinel-plugin` directory using the `--plugin-dir` flag,
or add it to your Claude Code settings:

```bash
# Run Claude Code with the plugin active
claude --plugin-dir /path/to/sentinel-plugin

# Or set in ~/.claude/settings.json
{
  "pluginDirs": ["/path/to/sentinel-plugin"]
}
```

Claude Code will set `CLAUDE_PLUGIN_ROOT` to the plugin directory when running hooks.

**First run:** When you open your first review, `render.js` will download and cache `diff2html` to `scripts/review-ui/vendor/`. This is a one-time setup (~300KB). After that, all reports work offline.

---

## Usage

### After any task — `/sentinel-review`

After Claude finishes a task, you'll see a reminder in the terminal:
```
╔══════════════════════════════════════════════════════════════╗
║  ✅  Task complete — 4 file operations recorded
║  Type  /sentinel-review  to generate your code review        ║
╚══════════════════════════════════════════════════════════════╝
```

Type `/sentinel-review` to:
1. Launch all 7 subagents in parallel
2. Generate a structured JSON report
3. Open a self-contained HTML review in your browser

### Proactive repo scan — `/sentinel-scan`

```
/sentinel-scan              # Run all 4 scanners (security, performance, usage, quality)
/sentinel-scan security     # Security Auditor only
/sentinel-scan performance  # Performance Scout only
/sentinel-scan usage        # Code Usage Inspector only
/sentinel-scan quality      # Code Quality Inspector only
```

---

## The 7 Subagents

| Agent | Model | What it finds |
|-------|-------|---------------|
| **Master Reviewer** | Opus | Intent vs reality, mid-task pivot artifacts, scope creep, missing deliverables |
| **Security Auditor** | Opus | SQL/command injection, auth bypass, data exposure, CORS issues — with complete attack chains |
| **Regression Hunter** | Opus | Active callers of deleted/renamed files, missing await after sync→async changes, broken import paths |
| **Performance Scout** | Opus | N+1 queries, blocking calls in async context, memory leaks, unbounded datasets |
| **Code Usage Inspector** | Opus | Wrong parameter count/order, missing required props, duplicate utility implementations |
| **Test Critic** | Sonnet | Stale mocks, tests that always pass, missing test coverage for changed code |
| **Code Quality Inspector** | Sonnet | Dead code, pivot artifacts, naming inconsistencies against observed codebase patterns |

---

## Review Reports

Reports are stored in your **project's** `.claude/reviews/` directory:

```
your-project/
└── .claude/
    └── reviews/
        ├── 2026-03-20-auth-refactor.json    # Queryable JSON
        ├── 2026-03-20-auth-refactor.html    # Self-contained HTML (shareable)
        ├── 2026-03-20-scan-security.json
        └── 2026-03-20-scan-security.html
```

Add `.claude/reviews/` to your `.gitignore` to keep review artifacts local:
```
# .gitignore
.claude/reviews/
```

### Query reviews with jq

```bash
# All CRITICAL findings across all reviews
jq '[.findings[] | select(.level == "CRITICAL")]' .claude/reviews/*.json

# All deleted files
jq '[.changes[] | select(.operation == "delete")]' .claude/reviews/*.json

# Tasks where deliverables were missing
jq 'select(.intent_vs_reality.missing | length > 0) | {task: .meta.task, missing: .intent_vs_reality.missing}' .claude/reviews/*.json

# All security findings
jq '[.findings[] | select(.found_by == "security-auditor")]' .claude/reviews/*.json
```

---

## Configuration

Edit `sentinel-plugin/.claude-plugin/plugin.json` to change model assignments:

```json
{
  "settings": {
    "models": {
      "deep_reasoning": "claude-opus-4-6",
      "pattern_matching": "claude-sonnet-4-6"
    }
  }
}
```

Set both to `claude-opus-4-6` for maximum quality.
Set both to `claude-sonnet-4-6` for cost efficiency.

---

## UI Features

The review browser UI includes:

- **Dark/light mode** — default dark, toggle persists across sessions
- **Live search** — filters findings, changes, and next steps in real-time
- **Severity filter chips** — show/hide by CRITICAL, HIGH, MED, LOW, DISCUSS, UNCLEAR
- **Agent filter** — click any agent name to see only their findings
- **Copy as Markdown** — exports the findings table as a Markdown table
- **Keyboard shortcuts:**
  - `/` — focus the search box
  - `j` / `k` — navigate findings rows
  - `Esc` — clear search
- **Diff viewer** — side-by-side diff for every changed file (diff2html)
- **Animated stats** — count-up animation on summary cards
- **Print mode** — clean print stylesheet (hides nav, expands all cards)

---

## File Structure

```
sentinel-plugin/
├── .claude-plugin/plugin.json      # Plugin manifest
├── skills/sentinel-review/SKILL.md # 10-step review skill
├── commands/
│   ├── sentinel-review.md          # /sentinel-review command
│   └── sentinel-scan.md            # /sentinel-scan command
├── hooks/hooks.json                # PostToolUse + Stop hooks
├── agents/
│   ├── master-reviewer.md
│   ├── security-auditor.md
│   ├── regression-hunter.md
│   ├── performance-scout.md
│   ├── code-usage-inspector.md
│   ├── test-critic.md
│   └── code-quality-inspector.md
└── scripts/
    ├── track_change.py             # Records file operations
    ├── trigger_review.py           # Reminds user after task
    ├── open_review.py              # Generates + opens HTML report
    └── review-ui/
        ├── render.js               # Builds self-contained HTML
        ├── template.html           # Full UI with all rendering code
        └── vendor/                 # Auto-created on first render
```

---

## How It Works

1. **During your task:** Every file write, edit, or bash command fires the `PostToolUse` hook → `track_change.py` appends an entry to `.claude/reviews/tmp/session-timeline.json`

2. **Task completes:** The `Stop` hook fires → `trigger_review.py` counts meaningful operations and prints a reminder

3. **You run `/sentinel-review`:** The skill reads the timeline, builds a conversation summary, launches all 7 subagents simultaneously (not sequentially), writes its own `changes[]` analysis while waiting, merges all findings, writes the final JSON, and opens the HTML report

4. **The report:** A fully self-contained HTML file that works offline and can be shared as-is

---

*Built with 🛡️ Sentinel — the peer review layer for Claude Code*
