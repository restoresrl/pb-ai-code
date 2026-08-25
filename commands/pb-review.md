---
description: Run a structured code review on a PowerBuilder target. Frames the work, builds a scoped context pack, validates understanding, writes a plan file, then hands off to pb-apply-plan for the edit loop.
argument-hint: <target> — entry triple, .pbt path, .pbl path, or free-form intent (e.g. "the n_logger chain")
---

# `/pb-review` — PowerBuilder code review and plan generation

Run the **`pb-review`** flow. The target the user gave is:
**`$ARGUMENTS`**

The complete instructions are the `pb-review` skill — read
[`../skills/pb-review/SKILL.md`](../skills/pb-review/SKILL.md) now and
follow it end to end. This file is only the entry point; it
deliberately does not restate the flow, so there is one place to fix
when it changes.

In outline, so you know what you are committing to: pre-flight
(`pb_workspace_info`, then the ORCA session) → Step 0, frame the work
with the user → Step 1, build the context pack → Step 2a, the
understanding gate → Step 2b, the review itself → Step 3, write the
plan file → Step 4, hand off to `pb-apply-plan`.

Two things not to shortcut: **Step 0 is always interactive**, even when
`$ARGUMENTS` is already a precise entry triple, and **Step 2a waits for
the user to confirm your understanding** before any finding is written.

If `$ARGUMENTS` is empty or unintelligible, ask the user to restate.
Do not guess a target.
