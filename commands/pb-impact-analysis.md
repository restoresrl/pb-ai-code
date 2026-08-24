---
description: Analyse the blast radius of a proposed PowerBuilder change before editing. Finds callers, descendants, dynamic uses, and coverage gaps without changing the workspace.
argument-hint: <target and proposed change> (for example, "rename core.pbl::f_lookup:function")
---

# `/pb-impact-analysis` PowerBuilder change impact

Analyse: **`$ARGUMENTS`**

Read
[`../skills/pb-impact-analysis/SKILL.md`](../skills/pb-impact-analysis/SKILL.md)
and follow it end to end. This command is only an entry point; the skill owns
the workflow.

Resolve both the affected entry and the proposed change before querying the
workspace. If either is ambiguous, ask rather than choosing a similarly named
entry.

This is a read-only analysis. Report the caller-discovery mode, `scanned N/M`,
and every target or library that could not be checked. Do not describe a fast
or capped pass as complete.
