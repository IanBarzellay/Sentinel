---
description: >-
  Generate a structured code review for the current task session.
  Launches 7 specialist subagents, scores risk, and opens a browser UI.
  Run this after completing any task where you want a peer review.
---

# Sentinel Review Command

Check whether file changes were recorded this session.

If `.claude/reviews/tmp/session-timeline.json` does not exist or contains an empty array,
tell the user:
> "No file changes recorded for this session. Make some changes first, then run /sentinel-review."

Otherwise, run the `sentinel-review` skill exactly as specified in `skills/sentinel-review/SKILL.md`.
Follow all 10 steps in order without skipping or abbreviating.
