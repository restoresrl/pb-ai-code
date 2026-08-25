---
name: plan-file-contract
status: populated
description: The normative schema of a .pb-review plan file: fields, status vocabulary, CHANGELOG recording, and which skill writes what.
---

# The plan file contract

A plan file under `.pb-review/` is written by one skill and rewritten by
another. [`pb-review`](../skills/pb-review/SKILL.md) produces it;
[`pb-apply-plan`](../skills/pb-apply-plan/SKILL.md) consumes it and writes
back into it as fixes land. Between them sits a schema neither owns.

**This page is that schema, and it is normative.** Where a skill's prose
disagrees with this page, this page is right and the skill has drifted.

## Why it exists as a separate page

The two skills were originally written against each other's prose rather
than against a shared definition, and drifted the way that always drifts:
a field the producer emits and the consumer never reads, a field the
consumer is told to write and nobody tells it to. Both were found the
first time the chain was run end to end, not by reading either skill.

The failure is quiet in both directions. A field the consumer ignores
does not raise an error; it produces the wrong answer on the one
workspace where it mattered. So the fix is not a better sentence in
either skill: it is one list, in one place, that both cite.

## Required fields

Every finding carries these. A plan file missing one is malformed.

| field | values | notes |
|---|---|---|
| `id` | `fix-01`, `fix-02`, … | unique within the file; never renumbered, because plan and release-note links use these anchors |
| `entry` | `lib::name:type` | the entry triple. `lib` is a **bare basename**: see `library_path` |
| `kind` | `bug-risk` \| `refactor` \| `style` \| … | others sort after the three named ones |
| `priority` | `high` \| `medium` \| `low` | |
| `depends_on` | list of `id`s | must be applied first |
| `depends_on_confidence` | `parsed` \| `user-augmented` \| `manual` | where the graph came from, **not** a judgement about the finding. Older plans spell it `confidence`; accept that and say you did |
| `evidence` | `code-read` \| `verified-in-docs` \| `unverified-semantics` | the judgement about the finding. `pb-apply-plan` gates on it. Missing on old plans: treat as `code-read` and say you assumed it |
| `status` | see below | a review always writes `pending` |

## Optional fields

| field | written by | notes |
|---|---|---|
| `library_path` | `pb-review` | absolute path of the `.pbl`. **Required whenever the queue spans more than one library**: `entry:` carries a bare basename and two libraries in one workspace can share one. **`pb-apply-plan` must prefer this over anything derived from `entry`** |
| `outside_source_tree` | `pb-review` | `true` when the finding lands in a vendored library. `pb-apply-plan` gates on it, per finding |
| `experiment` | `pb-review` | **required when `evidence: unverified-semantics`**: the test that would settle the premise, concretely enough to run |
| `function`, `lines` | `pb-review` | narrow the location |
| `effort_estimate` | `pb-review` | `small` \| `medium` \| `large` |
| `tag` | `pb-review` | free-form labels |
| `also_in` | `pb-review` | `[entry_triple, …]`: the same fix concept on secondary entries. Primary `entry` first, then these in topological order |
| `requires_discussion` | `pb-review` | `true` when the fix is a **choice**, not a pre-decided patch. Use with `decision_options` |
| `decision_options` | `pb-review` | `[{label, summary}, …]` |
| `chosen_option` | `pb-apply-plan` | the `label` the user picked. Required once a `requires_discussion` finding is decided |
| `skip_reason` | `pb-apply-plan` | free text. Required when `status` is `skipped` or `failed` |
| `applied_in` | `pb-apply-plan` | the entries that took a `partial` multi-entry fix |

## Status vocabulary

The full set. `pb-review` only ever writes `pending`; every other value is
written by `pb-apply-plan`.

| status | meaning | on resume |
|---|---|---|
| `pending` | not yet attempted | attempted |
| `applied` | landed and compiled | skipped |
| `skipped` | the user declined it | skipped |
| `failed` | attempted, did not compile, **reverted** | skipped: so a repeat run does not re-apply a patch already known not to build. Pair with `skip_reason` |
| `deferred` | set aside pending an answer: what an unattended run writes for `requires_discussion` and `unverified-semantics` | **treated as `pending`**, which is the whole point |
| `partial` | a multi-entry fix that landed on some entries and not others | attempted for the remainder. Pair with `applied_in` |

## The `**Applied**` section

`pb-review` leaves the field absent and says it is *written by
`pb-apply-plan`*. So `pb-apply-plan` must write it: this is the
instruction, since the consumer's own step list once omitted it and
three fixes out of four landed without one.

Write it into the finding body **whenever a fix reaches `applied` or
`partial`**, recording what actually landed. **Suggested fix** stays as
written: the difference between what was proposed and what was needed is
the part worth keeping. When a `requires_discussion` finding is decided,
name the option taken.

```markdown
**Applied** *(2026-08-14, option `keep`)*: <what actually landed>
```

## CHANGELOG recording

`pb-review` does not write `CHANGELOG.md`. A review can produce findings
that are declined or deferred, so recording them as release work before an
import succeeds is misleading.

`pb-apply-plan` appends a normal Keep a Changelog bullet only when a finding
reaches `applied` or `partial`. The bullet includes the finding id and a link
to the plan anchor. It does not add checkbox markers, rewrite existing
released sections, or record `pending`, `deferred`, `skipped`, or `failed`
findings. The YAML `status` field is the authoritative progress record; the
changelog is release history.

Before appending, the skill checks the plan id or anchor so a resumed run does
not duplicate an entry. Release promotion is separate and reviews all project
changes under `[Unreleased]`, not only the current plan.

The plan's YAML `status` is the only authoritative record of progress. A
changelog entry means that the corresponding change actually landed; it does
not mean that every finding in the plan was accepted.

## Cross-references

- [`pb-review`](../skills/pb-review/SKILL.md): writes the plan file.
- [`pb-apply-plan`](../skills/pb-apply-plan/SKILL.md): consumes and rewrites it,
  and records successful fixes in `CHANGELOG.md`.
- [`wiki-notes`](wiki-notes.md): the `## Notes for the wiki` section of the
  same file, and the trip back into this repository.
