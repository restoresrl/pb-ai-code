# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Tags on this repository are what a team pins to. The version here selects the
whole toolchain: which skill bundle, and — through the pinned URLs in
`harness/` — which `pb-orca-mcp` and which `pb-format`. Two developers
installed from the same tag have the same setup, and the marker file the
installer leaves in a target records which tag that was.

## [Unreleased]

## [0.1.10] - 2026-08-12

### Corrected

- **`pb-appeon-index` refused to run on Python 3.10**, which `requires-python`
  says it supports. `load_config` carried a runtime guard raising
  *"requires Python 3.11+ (uses tomllib)"* — true when it was written, and
  left behind when the import was given a `tomli` fallback in v0.1.9. A guard
  that rejects the oldest interpreter the package claims to support is a
  contradiction, and it made the Appeon index unusable there rather than
  merely untested.

  **Found by CI on its first run, which is the whole argument for having it:**
  no local run could have caught it, this machine being on 3.14. Eight
  releases had gone out without anyone executing this code path on the
  version it advertises. Verified afterwards on a real 3.10 interpreter — 14
  tests, green.

## [0.1.9] - 2026-08-12

### Added

- **CI.** This repository had none: eight releases went out in a day, gated
  by a local run on one machine — the same trust that had just turned out to
  be misplaced next door, where three tags shipped on a red build because
  `ruff format --check` was never run and nobody looked.

  Windows, Python 3.10/3.11/3.12, and the four commands as separate steps.
  The format check gets its own step deliberately: it is the one that gets
  forgotten, and a step that fails by name is harder to overlook than a line
  in a script.

- **The dead-link check is a test now** (`tests/test_links_resolve.py`),
  rather than a script in a session scratchpad. It has found something every
  time it has run — 28 dead links in an installed bundle in August while the
  repository itself was clean, five more the day the wiki-notes guide was
  added, one pseudo-link in prose.

  Two tests, because the canonical tree proves little on its own: the
  installer copies the documentation elsewhere and rewrites the links, so a
  link can be right here and dead in the only place a consumer reads it. The
  second runs the installer into a temporary directory for both harness
  layouts and checks what lands. That is why CI is on Windows.

### Corrected

- Paid the lint debt that would have made CI red on its first run: 14 `ruff`
  findings, 5 files needing `ruff format`, 7 `mypy` errors. All in the two
  local tools, none in the kit itself. The substantive ones were a `tomllib`
  import with no 3.10 fallback — so the package could not have been installed
  on the oldest Python it claims to support — and BeautifulSoup element
  narrowing, where `find()` may return a `NavigableString` that has no
  `.get`. The rest was formatting and long SQL lines.

  A CI that starts red teaches people to ignore the mail, which is how three
  tags shipped on a red build in the first place.

### What this does not do

None of the defects found this week would have been caught by any of it. The
26 from the unattended review rounds, the `.pbl` holding LF, the gate that
penalised findings for being verified, the vendored library adopting a
namesake's projection — all semantic, all false statements about how
PowerBuilder behaves. No static check sees those. What finds them is running
the thing against a real workspace.

## [0.1.8] - 2026-08-11

### Corrected

- Re-pinned `pb-orca-mcp` to **v0.2.8**, the first green build since
  2026-08-09. Nothing in v0.2.5 through v0.2.7 was functionally wrong — the
  lint job's `ruff format --check` had been failing while the tests and
  `ruff check` passed — but a tag pointing at a red build is worth less than
  a tag, and the pin should name one that is green.

  Worth recording as a process failure rather than a formatting one: the
  sibling's `CONTRIBUTING.md` listed all four required commands the whole
  time, three were being run, and nobody looked at CI after pushing. This
  repository has **no CI at all**, so its releases have only ever been gated
  by a local run on one machine — which is the same trust that just turned
  out to be misplaced next door.

## [0.1.7] - 2026-08-11

### Corrected

- Re-pinned `pb-orca-mcp` to **v0.2.7**, which stops a vendored library from
  adopting the sources of an unrelated library that shares its basename. That
  defeated `outside_source_tree` — the check whose whole job is to keep an
  edit out of a dependency that gets replaced wholesale — and an export
  without `dest_dir` would have overwritten the other library's sources.

  Found on the first workspace with genuine vendored dependencies, during the
  install verification. The synthetic workspace built two days earlier to
  exercise exactly this path could not produce it: it had no basename
  collision, because nobody thinks to build one.

## [0.1.6] - 2026-08-11

### Added

- **A route back for what a project learns.** The knowledge base is
  installed as a snapshot, which is what keeps every project on one version
  — and means an agent that discovers something cannot write it down where
  it works. Two skills already told it to record the discovery under
  "Notes for the wiki", and **that section did not exist**: the plan
  template never defined it, so the documented fallback pointed at nothing.

  It exists now, with six fields and two that carry the weight.
  `observed-against` is the kit commit the note was new against, read from
  the installer's marker, so whoever collects it can tell a discovery from
  something documented since. `evidence` is the gate: `compiled clean`
  names the call that proved the claim, `observed only` says it was seen
  but not confirmed. Both are worth writing; only the first is applied
  without someone reproducing it, which is the difference between a
  knowledge base that stays true and one that accumulates folklore.

  `pb-apply-plan` harvests at the end of a run, because that is where the
  compiler has just spoken and where the evidence therefore exists.

- [`docs/wiki-notes.md`](docs/wiki-notes.md) — how notes are produced,
  collected and turned into wiki changes, including how to write one that
  survives contact with the person applying it.

  It also says why the collection is manual on purpose. Automating the
  *decision* to contribute is the wrong end of the problem: a mechanism
  that opens a pull request per note yields, after a month, twenty
  unreviewed pull requests and the illusion of a working loop — at which
  point nobody reads the plan files either. A collector belongs after
  three or four real notes have shown what notes actually look like.

- The installer copies loose documentation files, not only trees. Found by
  installing and counting: the skills linked the new guide from the exact
  moment a reader is ready to act on it, and in a consumer that was **five
  dead links**, the guide being the one page the consumer needs most.
  Verified at zero dead links in the repository and in both installed
  layouts.

## [0.1.5] - 2026-08-11

The recovery paths, which four rounds of review had never reached because
nothing ever went wrong. Built the failures on purpose — a fix that will not
compile, a dependency cycle, a multi-entry fix, a decision with no patch body,
a vendored library — and ran the kit at them. **26 defects, five blocking.**

### Corrected

- **After a compile error there was nothing to revert to.** Step (a) exports
  into the projection itself on a `ws_objects` project, step (b) edits that
  file in place, so once the patch is written the pre-fix source exists
  nowhere — and `git checkout` is not a fallback, because this skill never
  commits a fix and `HEAD` predates every fix already applied in the run. On a
  queue of ten, a failure at fix-07 meant losing fixes 01 to 06 or shipping a
  library that does not compile. Measured, not reasoned: the `.pbl` took the
  broken source, the projection held it too, and the two **agreed** — on
  uncompilable code, with `git status` showing two ordinary modified files.
  A snapshot is taken before the edit now, and "revert" means re-import it.
- **A skipped finding could never come back.** An unattended run set
  `requires_discussion` to `skipped`; Step 4 walks `pending` only; the one
  sentence about re-opening covered `applied`; and the pre-flight forbids
  hand-editing status. So "run it overnight, answer in the morning" — the
  normal shape of unattended work — was undefined. There is a `deferred`
  state now, which a resume treats as `pending`. `skipped` stays terminal.
- **A chosen `decision_option` is prose, and the skill said to treat it as the
  fix body.** There is no body: the option is `{label, summary}`. Someone has
  to author the patch, which made this the one place in the flow where the
  most unreviewed code gets written — and (c2)'s guarantee that "the diff
  shown is what the user agreed to" is false here, because the user agreed to
  a label and saw no diff. It returns the finding to draft now, and an
  unattended run stops there whatever the evidence says.
- **`function_object` was rejected as an entry type**, which is a hard stop on
  every global-function finding. Fixed in `pb-orca-mcp` v0.2.6, which this
  release pins.
- **Halting the queue on the first compile error stranded everything else**,
  including findings with no relation to the failure. Now: revert it, mark it
  `failed`, carry on with the independent remainder — and stop the run on the
  second failure, because one is a bad patch and two is a bad assumption.
- The tie-breaker called **"Priority" ranked `kind`**, so the required
  `priority` field never affected the order at all. Two `bug-risk` findings on
  one entry — the common case — were left to document order by accident.
- **The compile diagnostics do not have the shape the skill described.**
  `message_number` empty, `column` always `0`, `line` relative to the function
  rather than the file, and the context headers carrying `level_name: "error"`
  while the real errors carry `unknown(4)`. Presented literally, the headers
  read as failures and the failures read as unknown.
- The pre-flight's `.pbl` line-ending check needs a session that the *next*
  step opens — the same ordering error already fixed in `pb-review`, still
  present here.
- A `CHANGELOG.md` with no checkbox bullets left the apply loop with nothing
  to tick and no instruction, so a run applied three fixes and **the
  repository recorded none of it**. It creates the bullet now.
- A cycle halt wrote nothing to disk, so a resume re-derived the identical
  halt and nothing distinguished "blocked" from "never run".
- Nothing looked at sibling plan files, so one plan silently undid a finding
  another had recorded as `applied`, leaving that plan describing an edit no
  longer in the source.
- "The first line of the function body" is ambiguous on disk — PowerBuilder
  puts the first statement on the signature line after the `;` — and following
  it displaced a declaration past its use, turning a one-line guard into six
  compile errors.
- Plus the vendored-library work in the previous commit, and the smaller ones:
  a `failed` status, `contract` and other unlisted `kind` values, the
  unattended run-mode field, tie-breakers that assume a context pack, and a
  branch rule that was undecidable on a repository with one branch.

### Verified working

The two pre-flight repairs, including the "1 of N entries holds LF"
prediction — it was 1 of 3 queued entries, and the other two would have said
"nothing to do". The `also_in` multi-entry path. The file loop round-tripping
BOM and CRLF intact on every successful import. And the cycle halt itself,
which correctly refuses to guess: both edges were over-declared, the skill
could not know that, and it did not pretend to.

## [0.1.4] - 2026-08-09

Four unattended runs against a real PowerBuilder library, each on a fresh
clone, each asked to report every place the kit made it guess. They found 21,
13, 6 and 2 defects; the fourth found none blocking and none serious. This
release is the last two, plus the three rounds before it.

### Corrected

- A skip in the apply loop rendered as `- [~] skipped: <reason>`, replacing
  the CHANGELOG bullet's fix id, its description and its link to the plan
  anchor — the anchor `pb-review` promises never to renumber precisely because
  the CHANGELOG points at it. The box changes; the bullet stays.
- Re-pinned `pb-orca-mcp` to **v0.2.5**, which documents that the `bytes` an
  export reports counts the source text and not the file, so the byte-identity
  check this kit prescribes no longer looks like it fails on every entry.

### Still unproven

Four rounds exercised the cautious paths and never the recovery ones. Nothing
failed to compile, no dependency cycle arose, no `also_in` fix reached the
apply stage, and no library was `outside_source_tree` — the test project has
no vendored dependency, so it cannot produce one. The kit stops correctly; it
has not been shown to recover correctly. Worth knowing before pointing it at
something that matters.

## [0.1.3] - 2026-08-09

### Corrected

- **v0.1.2 told people to protect their sources the wrong way.** The new
  line-ending guidance said to add `*.sr* binary`. It stops the translation,
  and it also implies `-diff`, so git answers `Binary files differ` for every
  change to a PowerBuilder object — trading silent drift for an unreadable
  diff, and discarding the reason a project keeps a `ws_objects/` projection.
  Now `*.sr* -text`, with `binary` kept for `*.pbl` and `*.pbd`. Fixed in the
  three skills and in
  [`encoding.md`](docs/pb-source-format/encoding.md); `pb-orca-mcp` v0.2.4
  carries the matching change and adds `sources_diffable`, so a repository
  where someone already made this mistake is told rather than left silent.

  The apply loop found it by following the advice literally, hours after the
  advice shipped. Guidance written and never executed is a hypothesis.

- This repository's own `.gitattributes` marked `.sr*` as `binary`, so it
  contradicted the skills it ships. It now models exactly what they
  recommend — verified with `git check-attr`, not by reading it.

## [0.1.2] - 2026-08-09

Everything here came out of the first real review the kit ran on a real
library. The findings about the *code* were the point; these are the findings
about the *kit*, which is what a dogfooding run is actually for.

### Added

- **The pre-flight now looks at git's line-ending translation.**
  `pb-orca-mcp` v0.2.3 makes `pb_workspace_info` report `source_protection`,
  and the skills act on it: `pb-context-build` reports it in the workspace
  summary, `pb-review` measures how far the normalization has already gone
  (`git ls-files --eol`, count the `i/lf w/crlf` files) and says it must be
  fixed before the apply loop, and **`pb-apply-plan` stops** when it is
  `unprotected` rather than writing a diff the user cannot trust.

  The review that found this ran against a repository where 56 of 61 sources
  were being normalized by git, and nothing in the chain said a word. A review
  is read-only, so it was harmless there — but it ends by handing off to the
  one skill that writes, and that skill would have produced changes invisible
  to `git status`.

  The `.gitattributes` fix is never folded into a fix commit: it rewrites every
  source in the index, so it would bury the change under a whole-tree diff.

- `tests/test_pins_in_sync.py` also checks bare `@vX.Y.Z` mentions, not just
  full URLs. The prose sentence explaining what the pin is for had drifted a
  version behind on the very release that added the URL check — the test
  watched the copies it knew about and missed the one in the sentence next to
  them. Changelogs are exempt: recording what a past version pinned is their
  job.

### Corrected

- **`appeon-query` told half the story.** The Appeon index is deliberately not
  configured by the installer — it needs an absolute interpreter path and a
  database each developer builds — but the skill's fallback only explained how
  to *populate* the index, not how to *add the server*, and pointed at a
  document that is not part of a vendored install. On the real run this cost
  two findings, which could not be checked against the language reference. The
  skill now carries the whole recipe inline, and `pb-review` states the rule
  that made those two findings safe anyway: **never assert PowerScript
  behaviour from memory inside a finding** — mark it unverified and name the
  experiment that would settle it. A wrong finding costs more than a missing
  one, because it looks exactly like a right one and arrives with an edit
  attached.
- `harness/claude-code/settings.json` pre-approves `mcp__pb-appeon-index__*`
  tools and names the server in `enabledMcpjsonServers`, for a server the
  installer never writes. That is intentional — it is inert until someone adds
  the server by hand, and then it saves them a step — but nothing said so.
  Now it does.

## [0.1.1] - 2026-08-05

Cut because v0.1.0 pins `pb-orca-mcp@v0.2.1`, which cannot start — so the tag
that is supposed to name a working toolchain named a broken one.

### Added

- **The installer now writes the MCP server configuration**, from a new
  canonical [`harness/mcp-servers.json`](harness/mcp-servers.json), instead of
  leaving readers to copy a JSON block out of the documentation. The pin is the
  reason: a block copied by hand stays on whatever tag was current the day it
  was copied, so the canonical file moves and nobody follows, and the pin
  quietly becomes documentation rather than configuration. Installed with the
  skills, the two are updated by one command and cannot drift.

  `-Harness claude-code` merges it into `<target>/.mcp.json`; `-Harness
  generic` prints it, because inventing a path for a client whose contract we
  have not verified would look like it worked. Servers the project already had
  are preserved — only the `pb-orca` key is written — and a target file that
  does not parse is left alone with the block printed for a manual merge.
  `-SkipMcpConfig` opts out entirely, for projects whose servers are managed at
  user scope.

  Consequence, and the point of the change: **a project using this kit commits
  nothing agentic.** No `.claude/`, no `.mcp.json`, no neutral stand-in file.
  Re-running the installer is the whole synchronization story. This repository
  now follows its own rule — its root `.mcp.json` is generated and gitignored,
  like `.claude/`.

- `tests/test_pins_in_sync.py`: every `restoresrl/<repo>@<tag>` reference in
  the tree must agree, and the file the installer materializes is the one that
  decides. A pin that disagrees with itself is worse than none — it tells two
  developers two different stories, each of which looks authoritative.

### Corrected

- Pinned `pb-orca-mcp` to **v0.2.2**. v0.2.1 could not start as an MCP server
  at all: `mcp` 2.0.0 removed `mcp.server.fastmcp` and the dependency had no
  upper bound. The CLI (`doctor`, `check`) kept working because it never
  imports that layer, which is exactly why this survived the install audit.
- **The optional Appeon doc index could not start either**, and for the same
  reason: `pb_appeon_index.mcp_server` imports `mcp.server.fastmcp`, and this
  repository's own `mcp` dependency had no upper bound. `__main__` imports that
  module at module scope, so it was not only `serve-mcp` that failed but every
  subcommand — including the `pb-appeon-index update` that `docs/install.md`
  tells you to run to build the database in the first place. Pinned `mcp<2`,
  and added a test that builds the server and registers its four tools, since
  the whole suite was green while the CLI could not import.
- The antipattern catalog's index linked `/pb-review` at
  `../../commands/pb-review.md`, which does not exist in a `-Harness generic`
  install — that harness has no commands directory. Points at the skill
  instead, which every layout has.

## [0.1.0] - 2026-08-05

First tagged release. Nothing is published to any package index; the delivery
mechanism is a git clone plus `scripts/install-skills.ps1`.

### Added

- **Seven skills** in [`skills/`](skills/), in the
  [Agent Skills](https://agentskills.io) `SKILL.md` format so any skill-aware
  assistant can load them: `pb-review` (structured code review producing a
  persistent plan file), `pb-apply-plan` (the confirm-per-fix edit loop),
  `pb-context-build` (a budgeted context pack out of a monolithic workspace),
  `pb-scaffold` (validated minimal bodies for six entry types), `pb-src-format`
  (the on-disk source format), `pb-format` (style normalization), and
  `appeon-query` (language and runtime API lookups).
- **Slash-command wrappers** in [`commands/`](commands/) — thin by design: each
  delegates to the skill of the same name, so nothing is lost on an assistant
  that has no slash commands.
- **A PowerScript antipattern catalog** under
  [`docs/pb-antipatterns/`](docs/pb-antipatterns/): six hazards that compile
  cleanly and bite in production, each with a reproduction and an idiomatic
  fix. Two of them cite Appeon's own SDI application template, so every
  application scaffolded from the wizard carries them.
- **A reverse-engineered `.sr*` format wiki** under
  [`docs/pb-source-format/`](docs/pb-source-format/): one page per entry type
  plus the two cross-cutting ones, encoding and style conventions. No upstream
  specification exists, so the pages carry a `status` field and an open-questions
  section, and grow as cases are met.
- **`tools/pb-appeon-index/`** — scrapes `docs.appeon.com` once into a local
  SQLite FTS5 database and serves it as four MCP tools. A language lookup costs
  roughly 400 tokens instead of several thousand. Optional; the `appeon-query`
  skill says so when the index is absent rather than guessing.
- **`tools/pb-source-analyzer/`** — bootstraps the format wiki from a real
  `.sr*` corpus, anonymizing project identifiers on the way in.
- **`scripts/install-skills.ps1`** — materializes the canonical files into
  whatever directory an assistant reads (`-Harness claude-code` or `generic`),
  vendors the two documentation trees beside the skills, rewrites their links to
  match, and leaves a marker recording the source commit.
- **[`docs/install.md`](docs/install.md)** — a Quickstart that is the whole
  sequence with nothing explained, then the reasons: per-client MCP config
  locations, how to verify the stack before trusting it, and what to do when an
  assistant has neither slash commands nor skill discovery.
- **[`AGENTS.md`](AGENTS.md)** in the cross-tool
  [agents.md](https://agents.md) format. One agent-instruction file, no
  per-assistant variant.

### Notes

- **Agent- and model-agnostic by construction, not by aspiration.** The
  canonical artefacts live in agent-neutral directories; everything under
  `.claude/` is generated and gitignored. Cross-repository links are URLs, and
  interactive prompts inside skills are written in neutral English with the
  standing instruction to speak the user's language.
- **Verified from a clean clone.** All three repositories were cloned into an
  empty directory and the documentation followed as written, which is how the
  install command was found to be broken (`cryptography` stopped publishing
  32-bit Windows wheels, and this stack must run x86 for `pborc.dll`), and how a
  vendored install was found to be missing the knowledge base its own skills
  link to.
- **Exercised end to end once**, on a small real workspace: pre-flight, scope
  framing, context pack, understanding gate, review, plan file, CHANGELOG entry,
  and the apply loop through `pb_object_export_file` → edit →
  `pb_object_import_file`. That run found four defects in these skills, all
  fixed here. It has not yet been run against a large legacy target, so the
  budget caps, caller discovery at size, and `outside_source_tree` handling are
  written but unproven.
