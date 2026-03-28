# 🛡️ Sentinel

### The automated code review layer for Claude Code.

Sentinel silently watches every file change Claude makes during a task. When the task ends, one command launches **7 specialist AI reviewers in parallel** — security, performance, regressions, test coverage, code quality, and more — and opens a beautiful, interactive report in your browser in under a minute.

> **Think of it as a senior engineer doing a full pull-request review after every single Claude task — automatically.**

---

## Why Sentinel?

Claude Code is fast. That speed comes with a tradeoff: it's easy to miss what actually changed, introduce subtle bugs, or ship a security issue that looks fine at a glance.

Sentinel closes that gap.

- **7 eyes on every change** — each agent is a specialist with a narrow, deep focus
- **Parallel, not sequential** — all 7 run simultaneously; total time ≈ slowest single agent
- **Automatic change tracking** — no manual setup; hooks fire silently during your task
- **Beautiful reports** — dark-mode browser UI, expandable findings, diff viewer, keyboard shortcuts
- **Shareable & offline** — reports are self-contained HTML files, no server needed
- **Any project, any language** — agents read and reason about code, not syntax trees

---

## How It Works

```
Your task runs                     You type /sentinel-review
      │                                        │
      ▼                                        ▼
Every file write/edit/delete       7 specialist agents launch in parallel
is silently recorded                           │
      │                                        ▼
      ▼                              Findings merged, risk-scored,
On task end → reminder printed      and written to JSON + HTML
                                               │
                                               ▼
                                    Browser opens with full interactive report
```

**Three commands cover everything:**

| Command | When to use |
|---------|-------------|
| `/sentinel-review` | After any Claude task — reviews exactly what changed |
| `/sentinel-scan` | Anytime — full repo audit, no task context needed |
| `/sentinel-scan security` | Target a single scanner: `security` · `performance` · `usage` · `quality` |

---

## The 7 Reviewers

Each agent runs on the model tier matched to its task. Deep reasoning agents use **Claude Opus**, pattern-matching agents use **Claude Sonnet**.

| Agent | Model | What it finds |
|-------|-------|---------------|
| 🧠 **Master Reviewer** | Opus | Intent vs. reality — did Claude actually do what you asked? Scope creep, missing deliverables, mid-task pivots |
| 🔒 **Security Auditor** | Opus | SQL injection, auth bypass, exposed secrets, CORS misconfiguration — with full attack chains and step-by-step reproduction playbooks |
| 🔁 **Regression Hunter** | Opus | Callers of renamed/deleted functions, broken imports, missing `await` after sync→async refactors, type contract violations |
| ⚡ **Performance Scout** | Opus | N+1 queries, blocking I/O in async paths, unbounded dataset loads, memory leaks — with reproduction scenarios |
| 🔍 **Code Usage Inspector** | Opus | Wrong argument order, missing required props, duplicate utility implementations, deprecated API usage |
| 🧪 **Test Critic** | Sonnet | Stale mocks, tests that can never fail, missing coverage for changed code, test file drift |
| ✨ **Code Quality Inspector** | Sonnet | Dead code, naming inconsistencies against your codebase patterns, structural anti-patterns, leftover pivot artifacts |

---

## The Report

Every review opens as a **self-contained, offline HTML file** — no server, no login, shareable by drag-and-drop.

**What you get:**

- **Risk summary** — animated count-up cards for CRITICAL / HIGH / MED / LOW findings
- **Intent vs. Reality** — did Claude complete the actual goal?
- **Session timeline** — every file operation in order: created, edited, deleted, renamed
- **Findings table** — expandable rows with full detail panels per finding:
  - 📋 Description + 💡 Suggestion (prose explanation, not just code)
  - IntelliJ-style **current code → suggested code** diff boxes with line highlights
  - ⚡ **Reproduction Flow** — step-by-step attack/load playbook for security and performance issues, with copyable payloads
- **Git diff viewer** — side-by-side diffs for every changed file
- **Suggested tests** — concrete test cases grouped by file
- **Dark / light mode** — default dark, toggle persists in `localStorage`
- **Live search** — filters across findings, timeline, and diffs in real-time (`/` to focus)
- **Severity + agent filters** — zero in on what matters
- **Keyboard navigation** — `j` / `k` to move, `Enter` to expand, `Esc` to clear search
- **Copy as Markdown** — paste findings directly into GitHub issues or PRs

Reports are stored in your project's `.claude/reviews/` — both JSON and HTML, queryable or openable.

---

## Installation

**Requirements:** Claude Code · Python ≥ 3.8 · Node.js ≥ 18

```bash
# Clone the repo
git clone https://github.com/IanBarzellay/Sentinel.git

# Point Claude Code at the plugin
claude --plugin-dir /path/to/Sentinel
```

Or add permanently to `~/.claude/settings.json`:

```json
{
  "pluginDirs": ["/path/to/Sentinel"]
}
```

**First use:** When you open your first report, `render.js` downloads and caches `diff2html` (~300 KB, one time). Every report after that works fully offline.

---

## Output Format

Reports live in your **project's** `.claude/reviews/` directory:

```
your-project/
└── .claude/
    └── reviews/
        ├── 2026-03-28-add-auth-middleware.json   ← structured, queryable
        ├── 2026-03-28-add-auth-middleware.html   ← self-contained, shareable
        ├── 2026-03-28-scan-security.json
        └── 2026-03-28-scan-security.html
```

Add to your project's `.gitignore` to keep reviews local:
```
.claude/reviews/
```

### Query reviews with `jq`

```bash
# All CRITICAL findings across all reviews
jq '[.findings[] | select(.level == "CRITICAL")]' .claude/reviews/*.json

# Security findings only
jq '[.findings[] | select(.found_by == "security-auditor")]' .claude/reviews/*.json

# Reviews where deliverables were missing
jq 'select(.intent_vs_reality.missing | length > 0) | {task: .meta.task, missing: .intent_vs_reality.missing}' .claude/reviews/*.json

# All deleted files across all tasks
jq '[.changes[] | select(.operation == "delete")]' .claude/reviews/*.json
```

---

## Configuration

Edit `.claude-plugin/plugin.json` to control model assignments:

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

Set both to `claude-opus-4-6` for maximum depth. Set both to `claude-sonnet-4-6` for speed and cost efficiency.

---

## Under the Hood

- **Hooks** — `PostToolUse` fires on every Write/Edit/Bash and appends to a session timeline. `Stop` fires when the task ends and triggers the reminder.
- **Validation** — each agent's JSON output is validated before merging. Critical errors trigger an automatic retry (up to 2 rounds). Warnings are surfaced but never block the review.
- **Offline-first HTML** — `diff2html` is downloaded once to `vendor/` and inlined into every report at render time. Zero CDN calls at read time.
- **Language agnostic** — agents read code and reason about it; no parsers, no ASTs, no language-specific config.

---

*Built by [Ian Barzellay](https://github.com/IanBarzellay)*
