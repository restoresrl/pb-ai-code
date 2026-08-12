# Wiki notes — how the knowledge base learns

The two knowledge trees in this repository —
[`pb-source-format/`](pb-source-format/index.md), the reverse-engineered
`.sr*` file format, and [`pb-antipatterns/`](pb-antipatterns/index.md),
the catalog of PowerScript hazards — are not finished documents. They are
what has been observed so far, and the projects that use this kit meet
things they have not seen.

This page is about the trip back: how a discovery made while working on
somebody's PowerBuilder library becomes a change to the wiki everybody
installs.

> Reading this beside the skills, as `pb-ai-code-docs/wiki-notes.md`? Then
> you are in an installed snapshot — which is exactly the situation this
> page is about. Links to files that exist only in the `pb-ai-code`
> repository are given as URLs for that reason.

## The problem it solves

A project using this kit does not have the knowledge base. It has a
**snapshot** of it, installed as `<harness>/pb-ai-code-docs/`, which the
next install overwrites. That is deliberate — it is what keeps every
project on one version instead of on a slowly diverging copy — but it has
a consequence: **an agent that learns something cannot write it down where
it works.**

So the discovery has to be carried. A note in the review's plan file is
the vehicle, because the plan file is the one artefact that already
survives the session, sits in the project's own repository, and gets read
by a human.

## Where notes come from

Two skills produce them, at two different moments.

[`pb-src-format`](../skills/pb-src-format/SKILL.md) produces the
format ones. Its flow ends with *grow the wiki*, gated on the content
having compiled: a layout you merely read might be a typo, a layout that
went through `pb_object_import_file` with `errors: []` is a fact about
PowerBuilder.

[`pb-review`](../skills/pb-review/SKILL.md) produces the antipattern
ones, when it meets a hazard the catalog does not have. Those are usually
`observed only` — a recurring shape rather than something a compiler
confirmed.

[`pb-apply-plan`](../skills/pb-apply-plan/SKILL.md) harvests at the end of
its run, because that is where the compiler has just spoken. In practice
most format notes are written there, into the plan file the review
produced.

All three write into the same place: the `## Notes for the wiki` section
of the plan file under `.pb-review/`.

## What a note looks like

```markdown
## Notes for the wiki

### note-01 — userobject: binary tail after `end type` with an OLE control

- **page**: `pb-source-format/userobject.md`
- **section**: `Variants observed`
- **observed-against**: `pb-ai-code @ 0.5.0`
- **evidence**: `compiled clean` — `pb_object_import_file` returned
  `errors: []`, `sync: "ok"`
- **repro**: <the smallest snippet that shows it>
- **why it differs**: the wiki's canonical form ends at `end type`; this
  file carries an opaque block after it, which the IDE regenerates.
```

Six fields, and two of them do the work.

**`observed-against`** is the version of the kit the note was new
*against*. It comes from the marker the installer leaves next to the
skills — `.claude/_installed-from-pb-ai-code.txt`, the `# Version:` line,
with `# Source:` beside it naming the origin and the commit it was built
from. Without it, whoever collects the note has to re-establish whether
the thing is still undocumented; with it, that is a one-line check. This
is the reason the marker records a version rather than a date.

A marker written by the old PowerShell installer has no `# Version:`
line. There the version is the token after `pb-ai-code @` on the
`# Source:` line, and it is a short commit sha — which is why the
collecting step below accepts either.

**`evidence`** is the quality gate, and it has two values.
`compiled clean` means the claim was proved by the compiler, and names
the call that proved it. `observed only` means it was seen but not
confirmed. Both are worth writing. Only the first gets applied without
someone reproducing it — which is the difference between a knowledge base
that stays true and one that accumulates plausible-sounding folklore.

## What happens to a note

Today, deliberately, this part is manual: notes are read by a person
holding the `pb-ai-code` repository, and applied by hand.

That is not a placeholder for automation that was too hard. Automating
the *decision* to contribute is the wrong end of the problem: a
mechanism that opens a pull request for every note produces, after a
month, twenty unreviewed pull requests and the illusion of a working
feedback loop — at which point nobody reads the plan files either,
because the loop is "handled". A contribution mechanism is worth its
merge rate, not its volume.

What is worth automating is the tedious half — finding the right place
in the right page, checking the fact is not already documented since
`observed-against`, and writing a readable pull request. That is a
collector script, and it will be written once there are three or four
real notes to shape it against. Guessing the shape of notes nobody has
written yet is how you get a tool that fits nothing.

### Collecting them by hand, for now

1. Look in the plan files: `<project>/.pb-review/*.md`, section
   `## Notes for the wiki`.
2. For each note, check `observed-against` against this repository's
   history for that page. Resolve it first: a version is the tag `v<x>`
   (a `.dev`/`+g<sha>` one carries its commit in the local part), a bare
   sha is the commit. If the page changed since, read the change first —
   the fact may already be there.
3. Apply `compiled clean` notes to the named page and section. For
   `observed only`, either reproduce it first or record it under
   **Open questions** on that page, which is what that section is for.
4. Keep the repro snippet. A variant without one is an assertion; with
   one it is a test the next reader can run.
5. Update the page's `status` in its frontmatter if it moved: `stub` →
   `seeded` → `populated`.
6. Re-run `scripts/install-skills.ps1` wherever the kit is installed, so
   the projects get what was learned.

## How to use a note well

**Prefer the smallest true statement.** "A `.sru` with an OLE control
carries an opaque block after `end type`" is usable. "OLE controls make
`.sru` files weird" is not, and will be deleted by whoever tries to act
on it.

**Say where it was seen, and anonymize the rest.** The catalog's own
template asks for a "Where it has been seen" line, and the reason is that
a hazard with a real sighting is one a reader believes. Keep the date and
the mechanism, drop the names — this repository is destined to be public,
and a scrub in 2026-07 found product names on all six catalog pages
precisely because nobody had thought about it while writing.

**A note that turns out to be wrong is worth recording as wrong.** Move
it to **Open questions** with what was tried. The next person to meet the
same construction saves the hour you spent.

**When in doubt about the fact, do not write it as canonical.** The
format wiki distinguishes *Canonical form* from *Variants observed* for
this reason: one is what PowerBuilder always does, the other is what it
did in the case you saw. Putting a variant in the canonical section is
the one edit that makes the wiki actively misleading.

## Growing the format wiki wholesale

Notes are the incremental path. There is also a bulk one: the corpus
scanner in [`tools/pb-source-analyzer/`](https://github.com/restoresrl/pb-ai-code/blob/main/tools/pb-source-analyzer),
which is how the format pages were produced in the first place —
`scan → anonymize → aggregate → render` over a tree of real sources.

```pwsh
python -m pb_source_analyzer pipeline --root <a PB workspace> --target docs/pb-source-format
```

Worth doing when a codebase arrives that is structurally unlike the
existing corpus, since it re-derives the canonical forms by induction
rather than one observation at a time. The intermediate `scan.json`
carries real file paths and is gitignored; only the anonymized, rendered
output belongs in the repository.

## Cross-references

- [`pb-source-format/index.md`](pb-source-format/index.md) — the format wiki
- [`pb-antipatterns/index.md`](pb-antipatterns/index.md) — the hazard catalog
- [`install.md`](https://github.com/restoresrl/pb-ai-code/blob/main/docs/install.md) — why the installed copy is a snapshot
