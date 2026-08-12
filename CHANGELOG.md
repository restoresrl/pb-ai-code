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

### Added

- **A drafted request to Appeon**, `docs/appeon-index/redistribution-request.md`,
  asking for written permission to attach the built documentation index to
  releases. Unsent. It exists because the alternative to asking is
  interpreting a clause that is not ambiguous: the PowerBuilder manuals say no
  part may be "reproduced, transmitted, or translated in any form or by any
  means, electronic […] without the prior written permission of Appeon Inc.",
  and a database attached to a GitHub release is exactly that.

  Worth recording what the check found, since the question will come back: the
  documentation is free to read, `docs.appeon.com` publishes no `robots.txt`
  and carries no terms-of-use notice on the pages, so nothing forbids the
  local scraping the kit does today. Public access and redistribution rights
  are different things, and only the second one is withheld.

  Nothing changes in the meantime. The index is built locally, once per
  machine, and is not redistributed.


## [0.5.1] - 2026-08-12

One defect, found by watching a fresh session install the kit and report the
Appeon index as absent on a machine that has one.

### Fixed

- **Building the index required a clone, on a machine that already had the
  tool.** `pb-appeon-index` resolved its `config.toml` by walking three
  directories up from its own module. That lands on a real file inside a
  checkout and, from a wheel, on `<site-packages>/../config.toml`, which does
  not exist — so `uvx --from git+... pb-appeon-index update` died with a
  `FileNotFoundError` naming a path nobody could make sense of. Hence the
  recipe the installer printed began with `git clone`, and hence v0.5.0 could
  install the kit from anywhere but could not get it an index.

  `config.toml` now ships in the wheel and is found through
  `importlib.resources`, with the checkout path as the fallback. The whole
  recipe is one line:

  ```pwsh
  uvx --from git+https://github.com/restoresrl/pb-ai-code pb-appeon-index update --all
  ```

- **The default database path was relative to the working directory.**
  `docs/appeon-index/index.db` is right inside this checkout and meaningless
  anywhere else, where it would quietly build a second index next to whatever
  the user happened to be standing in. It is now
  `~/.pb-appeon-index/index.db` — what `mcp_server` already fell back to and
  what the installer looks for, so one database serves every project. A
  checkout whose index is where it has always been keeps using it: that path
  still wins when the file exists.

### Note on what this does not fix

A machine with no index still has to build one, and that means scraping
docs.appeon.com — one command now, but minutes rather than seconds. Shipping
the database as a release asset is what would make a clean install work
immediately, and that is a decision about redistributing scraped Appeon
documentation rather than a technical one. It stays deliberate: the kit builds
the index locally and does not redistribute it.


## [0.5.0] - 2026-08-12

The kit installs itself, from the project that consumes it. Until now you
cloned this repository and ran a PowerShell script that pointed at a target;
now you stand in your PowerBuilder project and run one command that needs no
clone at all:

```pwsh
uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code install
```

That inverts the direction of the whole thing, which is the point. The goal it
serves: a user opens their repository with an agentic editor, gives the agent
this URL, and the agent reads the instructions here and sets everything up. An
agent cannot follow instructions it cannot read, so **the three repositories
are now public** — there is no customer code in any of them.

### Added

- **`pb-ai-code`, a Python CLI, with `install` and `status`.** It ships in the
  wheel, so `uv` fetches it, builds it and runs it; it writes into the current
  directory. `status` reads the marker back with no network and answers in
  prose or, with `--json`, in a form an agent can check.

- **The kit travels inside the wheel.** This is the change that makes the rest
  possible, and it was not obvious: `[tool.hatch.build.targets.wheel]` packaged
  only the two Python tools, so a wheel built from a clean checkout carried 18
  files and **not one** that the installer needs — an installer with nothing to
  install. Six `force-include` mappings fix it, and there is a trap inside the
  fix: `force-include` ignores `.gitignore` **and** ignores `exclude`, both
  verified, so mapping the `docs` root would drag the 4.5 MB Appeon index into
  the wheel from any machine that had built one. The six paths are named one by
  one for that reason, and a test asserts the payload is set-equal to
  `git ls-files` over them, with no `*.db` anywhere.

- **A README section written for a machine.** Prerequisites with the command
  that checks each one, how to pick a layout, the command, a mechanical
  verification, what to say about restarting, and a branch for each way it
  fails. `AGENTS.md` points at it, since that is the file most harnesses read
  first.

- **The version comes from the tag**, via `hatch-vcs`. `pyproject.toml` said
  `0.1.10` while the tag was `v0.4.0` — invisible until the day the CLI stamps
  a marker from it, which is this day. Verified end to end: on a tag the
  distribution reports the release; one commit past, `0.5.1.dev1+g<sha>`, a
  build that says out loud it is not a release. CI needs `fetch-depth: 0` for
  it, because a shallow clone silently produces `0.1.dev1+g<sha>` with nothing
  but a `UserWarning`.

### Changed

- **`scripts/install-skills.ps1` is deprecated** and kept for one release so
  nobody is stranded mid-upgrade. Its description now says so, and two comments
  that had been contradicted by its own code — and by a commit message that
  recanted them — are corrected rather than carried into the port.

- **The MCP block is not the same JSON for every client**, and three documents
  in this repository said it was. Codex CLI wants TOML,
  `[mcp_servers.<name>]`; OpenCode fuses command and arguments into one array
  and spells the environment key `environment`; Continue is YAML with a `name`
  inside the entry; Aider has no MCP at all. Only Cursor shares Claude Code's
  shape. Corrected in `harness/README.md` and `docs/install.md`, because that
  sentence is exactly what makes someone paste a block into a file that cannot
  read it.

- **`docs/install.md` advertised a line the installer does not print.** The
  `pb-appeon-index configured -> <db>` sentence is the *marker's* value; stdout
  says `Appeon index      <db>` and a second line. Both are documented now, as
  what they are.

- **The marker's update recipe names the harness.** The old one named
  `-Target` and `-Harness`; a port that dropped the flags would tell a
  `generic` consumer to install a different layout on top of their own.

- The two planning documents are in English, as `AGENTS.md` requires of
  documentation.

### Verified rather than assumed

The port was checked by running both installers against identically seeded
targets — an existing `.mcp.json` with a third-party server, a differently
cased duplicate ORCA key, a `settings.json` that differs — and diffing
everything: the file set, the contents, the merged servers, stdout. For
`claude-code` they agree. Under `generic` there is exactly one difference and
it is deliberate: the marker moves out of the skills directory into the bundle
root, which is what two documents already described.

Along the way, two premises that were being taken on faith were measured.
`uv` **does** write PEP 610 `direct_url.json` for a VCS install — from a bare
URL with `commit_id` and no `requested_revision`, from a tag with the revision
verbatim — which is what the marker's `# Source:` line and its update recipe
rest on. And `git+file://` is not a substitute for testing the real URL: it
makes `uv` panic with `AmbiguousAuthority`.

### Fixed

Nineteen findings came out of an adversarial pass over the port. The four that
were losses:

- **A UTF-16LE `.mcp.json` was rejected.** PowerShell's `Get-Content -Raw`
  decoded it and rewrote the file as UTF-8; the port saw NULs, failed the
  strict parse and refused a perfectly good file. UTF-16LE is what `>` and
  `Out-File` produce in Windows PowerShell 5.1, which is the shell these shops
  still have.
- **A blank `--commands-dir` half-installed the target**, dying in the middle
  of the copy with an unhandled `FileNotFoundError` — the exact state the
  validate-everything-first rule exists to prevent. The whole family is closed
  now: a path component that is blank or whitespace-padded is refused, in one
  place, before anything is written. Worth recording why: a trailing space does
  not crash the PowerShell script, it exits 0 and creates *two* directories,
  one of them named with a trailing space that most Windows tooling cannot
  open. Silent corruption, not an error.
- **A `--skills-dir` not named `skills`** produced a bundle whose cross-links
  were dead: 13 links in 6 files spell that segment out. (The verification
  first said 59; the count was checked before it went into a permanent comment,
  and 59 is the number of *sibling* links between skills, which are unaffected.)
- **The coordinated document change was missing.** The marker's `# Source:`
  value is no longer a bare sha, and two documents told an agent to read it as
  one.

And one that killed the report mid-flight: **any character the console codepage
cannot encode.** On Windows a redirected stdout is opened with the ANSI
codepage and `errors='strict'`, so one accented character in a path truncated
the report with a traceback and left the target without a marker. PowerShell
was lossy but alive. It is lossy but alive again — and it fired on this machine
while the findings were being read, which is how it was caught.


## [0.4.0] - 2026-08-12

The installer now configures the Appeon doc index by itself. This removes
the last piece of the kit that a user had to wire up by hand, and with it
a dichotomy that was confusing on its own terms: one of the two MCP
servers arrived configured and the other arrived as a paragraph of
instructions, with nothing in the product explaining why.

### Added

- **`install-skills.ps1` writes the `pb-appeon-index` server entry.** It
  looks for three things in the checkout it is running from — the `.venv`
  interpreter, `docs/appeon-index/index.db`, and the `pb_appeon_index`
  module — and when all three are there it merges a server block into the
  target's `.mcp.json` with absolute paths and a `PB_APPEON_INDEX_DB`
  environment variable. The permission file already pre-approved the four
  `appeon_*` tools, so nothing else changes: the tools simply appear.

  The reason this could not be done before is worth recording, because it
  looks like an oversight and was not. `harness/mcp-servers.json` is
  committed and shared between machines, so it can hold `uvx --from
  git+...` but never `C:\Users\...\.venv\Scripts\python.exe`. What
  changed is noticing that the *target's* `.mcp.json` is neither
  committed nor shared — the installer generates it, the consumer
  gitignores it — and that the installer, running from the checkout, is
  the one component that knows all three paths. Absolute paths were never
  the problem; putting them in the wrong file was.

- **The installer says which way it went, on both paths.** With the index
  present: `Appeon index: pb-appeon-index configured -> <db>`. Without it:
  the missing pieces named, and the two commands that build it. The same
  line goes into the marker file in the target, so a later session that
  finds the tools absent can read why instead of guessing.

  This matters because the failure is silent by nature. A missing server
  is not an error anywhere — the agent just never sees four tools it was
  told to use, and the skill's fallback ladder quietly takes over.

### Changed

- **The database is referenced, never copied.** Every project points at
  the one file in the checkout, so `pb-appeon-index update` — a new PB
  release, say — reaches every configured project at once with no
  re-install. Re-running the installer is for changed skills, not for a
  changed index. Copying per project would have been the obvious
  implementation and the wrong one: N stale copies instead of one live
  file, and the update path would have needed a re-install nobody would
  remember to run.

- **The three places that documented the manual recipe now document the
  automatic one**: `skills/appeon-query/SKILL.md`, `docs/install.md` §3,
  and `docs/appeon-index/README.md`. The JSON block survives in the last
  of these, for anyone wiring up a client the installer does not know
  about, but it is no longer an instruction.

- **`harness/claude-code/settings.json`'s leading comment** explained why
  the installer did not configure this server. It now explains that it
  does, and that the permissions below are inert until the index exists.

- **`skills/pb-review/SKILL.md` pre-flight step 4** described absent
  `appeon_*` tools as "the normal state". It is now a state with one
  cause and a two-command cure, which is what a reviewer needs to be told.

### Testing

- `tests/test_installer_mcp_merge.py` asserted the exact set of servers
  after a merge, and this change broke it — correctly, since the set grew.
  Rewritten to assert the property instead of the snapshot: the project's
  own servers survive, ours is written, and the only key that may appear
  beyond those is `pb-appeon-index`. The exact-set form could not have
  been kept, because the index is gitignored: present on a developer's
  machine, absent on CI, so the true set depends on where the test runs.


## [0.3.1] - 2026-08-12

Four gaps in `pb-apply-plan`, found by pointing a hand-written plan file
at the loop with one finding per refusal gate. All four are cases the
skill described somewhere and then did not check.

### Corrected

- **`sources_diffable: false` was not gated.** The pre-flight stops on
  `source_protection: unprotected`, but a project can have a
  `.gitattributes` rule — so `source_protection` answers `protected` and
  the run proceeds — while that rule marks the `.sr*` files `binary`
  rather than `-text`. `binary` implies `-diff`, so every fix the loop
  applies comes back as `Bin 716 -> 718 bytes, 0 insertions, 0
  deletions`. Same harm as the case that *is* gated, arriving by a
  configuration the skill's own advice tells people to avoid. Measured
  on a fixture: `git check-attr diff` answered `unset`, a two-byte edit
  rendered as "Binary files differ". Now treated like `unprotected`,
  with the narrower repair — swap `binary` for `-text` on the source
  lines, no renormalize needed since the indexed bytes are already
  right.

- **Nobody said whether the plan or the workspace wins.** A finding can
  carry `outside_source_tree: true` from when the review ran;
  `pb_workspace_info` answers for now. `pb-review` said the loop "gates
  on it" — the flag — while `pb-apply-plan`'s pre-flight described
  gating on the live check. Plans are applied days or weeks after they
  are written, so the two routinely disagree. The rule is asymmetric:
  refuse when **either** says outside, since a library that became
  vendored since the review is the dangerous direction and a stale plan
  cannot know it — and report the disagreement, because it is evidence
  about the other findings in the same plan.

- **A dependency set to `deferred` did not block its dependents.** The
  topo-sort puts a dependency first; it never checks that the dependency
  landed. `skipped` cascades through the skip path and `failed` stops
  its dependents per the unattended table, but `deferred` — which is
  precisely what an unattended run writes for every
  `unverified-semantics` and `requires_discussion` finding — fell
  through both. The loop would walk past the deferred dependency and
  apply the fix that needed it. Step 4 now requires dependencies to be
  `applied`, and holds a blocked fix at `pending` with `blocked_by:`
  rather than mislabelling it skipped.

- **The required-field list rejected a real plan file.**
  `depends_on_confidence` is listed as required; plans written before
  the rename carry `confidence`. One of them is in this kit's own test
  fixture, and it also has no `evidence` field — which *was* handled.
  A resume that refuses to parse an aged plan is a resume that does not
  resume. The old spelling is now accepted as the same field.

- **Ticking CHANGELOG boxes assumed the boxes exist.** A hand-written
  plan has none. Note it once and carry on; do not invent the entry
  mid-run, since `pb-review` owns that file's structure.

## [0.3.0] - 2026-08-12

The write loop is now atomic, and the shape of it is documented with a
diagram. Everything below was measured against two live workspaces — one
with a `ws_objects` projection under git, one with neither — rather than
reasoned about.

**Why a minor bump.** The apply loop changes shape: the work happens in a
scratch directory, the project is written to only after a compile has
already succeeded, and a failed import is undone by restoring a file
rather than by re-importing. A queue that ran under 0.2.x lands the same
fixes, but what it leaves behind on failure is different.

### The guarantee

After each fix the `.pbl` has **either advanced by exactly that fix, or
is byte-identical to what it was before it**. There is no third state.

### Corrected

- **A failed import damages the compiled half of a `.pbl`, and the
  skill's recovery could not repair it.** A `.pbl` holds source *and*
  compiled p-code. Measured on one entry: a failed import grew the
  source by the edited line (`source_size` 3920 → 3962) while the
  compiled form **shrank by 1218 bytes** (`object_size` 6792 → 5574) —
  the event that failed to compile lost its p-code. So the entry is left
  with new text and a mutilated object, and the previous advice
  ("re-import the corrected file") reproduces the code with a fresh
  compilation timestamp instead of restoring what was there.

  The loop now snapshots the `.pbl` file before every import and copies
  it back on failure. Verified: source size, object size and
  `create_time` all return exactly, which no re-import can achieve.

- **The obvious verification was blind to the failure it was meant to
  catch.** Diffing exported sources — which 0.2.x's guidance
  recommended, and which this project used to check its own earlier
  work — returns the source half only, so an entry whose p-code is
  damaged exports byte-identical text.

- **Editing happened inside the project.** The export wrote the
  projection itself, so a fix was visible in `git status` before anybody
  had confirmed it, and a failure needed two files restored. Now the
  export goes to a scratch directory with an explicit `dest_dir`, the
  project receives a write only on success, and a `pbl_only` project
  does not even acquire a `.pb-orca/` working directory.

- **The rollback is no longer a question.** Leaving a library in the
  state a failed import produces is not a decision anyone would take, so
  the restore is immediate and automatic. The real decision — retry or
  abandon — is then made with the library already sound.

### Measured and documented

- **Importing from a scratch file still updates `ws_objects`.** This was
  doubted, and it was worth doubting: the earlier evidence came from an
  import whose source file *was* the projection, which proves nothing.
  Re-measured properly — `synced_files` carries the projection path and
  the file on disk changes. The sync follows the library, not the source
  path. On a project with no projection the response says
  `sync: "not_applicable"`. So the loop never copies anything into
  `ws_objects` by hand.

- **Overwriting a `.pbl` under a live ORCA session is safe.** The copy
  succeeds while the session holds the library, and the next export
  returns the restored content. No session recycling.

- **A `.pbl` hash is not an equality check**, and now the reason is in
  the format wiki rather than being folklore: the compiled half carries
  a compilation timestamp, so re-importing identical source yields
  identical sizes and different bytes.

- **Export just in time, never batched.** Two fixes on one entry — or
  one fix spread across `also_in` — would otherwise have the second
  editing text that lacks the first, and importing it would undo the
  first **with no error**. The one failure in this flow that no gate can
  catch, because the import succeeds.

- **Never pass PowerScript through a shell argument.** Git Bash rewrites
  arguments beginning with `//`, so a comment line arrives with one
  slash and becomes a syntax error. Found while testing this loop, on
  the loop's own test edit.

### Added

- A flow diagram of the write loop in `pb-apply-plan`, covering both
  project modes in one path — the only difference is whether there is a
  projection to keep in step, and the import handles that itself.
- A section in the format wiki's index on the two halves of a `.pbl`
  and what each one does under a failed import.

## [0.2.2] - 2026-08-12

### Corrected

- **A modified `.pbw` was being reported as if it meant something.** All
  three session-bearing skills said to mention it when the user looks at
  `git status` — `pb-context-build` went further and advised reverting
  it. That is wrong about how PowerBuilder workspaces behave: the
  `DefaultTarget` and `DefaultRemoteTarget` lines rewrite themselves the
  moment anybody opens the workspace in the IDE and selects a different
  target. No decision, no intent, and it happens constantly.
  `pb_set_current_application` producing the same edit is one cause among
  several, not a special one.

  Reporting it spends the reader's attention on a file that changes if
  you look at it sideways, and a stream of remarks about nothing teaches
  people to skim the ones that matter.

  **The one part of that file worth a word is the target list.** A
  `@targets` block that gained or lost an entry means the set of things
  the workspace builds has changed. The skills now say to check exactly
  that — with a one-line diff filter — and to stay silent otherwise. The
  rule runs in both directions: a local uncommitted `.pbw` edit that has
  *disappeared* is the IDE reclaiming its file, not an incident to
  investigate.

  Full rule in `pb-context-build` under *Session bring-up*; short form in
  `pb-review` and `pb-apply-plan`.

## [0.2.1] - 2026-08-12

### Added

The two catalog entries v0.2.0 identified and did not write. Both came
out of the same review as the rest of that release; the plan file holding
them was in a disposable clone, so they are recorded here from the
findings rather than from the note.

- **`exception-factory-not-thrown`** — `if err <> "" then f_make_ex(...)`:
  the exception is constructed and discarded, because a call in statement
  position is a legal expression whose value nothing has to use. Three
  things hide it: the compiler has no objection, an exception factory
  with a short name reads as an imperative in that position, and the
  function then carries on and returns success, so the failure surfaces
  somewhere else entirely. Seen in the `init()` of a persistence base
  class with 149 descendants, where a DataWindow build error was dropped
  and `init()` returned TRUE — the same file raises correctly twice a few
  hundred lines away, so it was a missing keyword, not a convention.
  Carries a grep recipe, because reading does not catch a defect whose
  wrong form is one word shorter than the right one.

- **`disablebind-defeats-bind-variables`** — `DisableBind=1` in the
  transaction's `DBParm` makes PowerBuilder substitute values into the
  statement text instead of binding them, so `:name` stays the syntax
  everyone trusts while no longer providing the property it is trusted
  for. The flag sits in a constructor two or three classes above any SQL,
  it is set for good reasons (`Identity='SCOPE_IDENTITY()'` requires it),
  and it applies to every statement on that connection.

  The page deliberately does **not** claim a vulnerability: whether
  PowerBuilder escapes as it inlines was not verified. It is written
  around the review lesson, which holds either way — read the
  transaction's `DBParm` before drawing a conclusion from the statement
  in front of you — plus the small experiment that settles it and the
  instruction to record the answer next to the flag.

New *SQL and data access* category. `throw-factory-loses-subtype` now
points at its sibling instead of saying it has none.

## [0.2.0] - 2026-08-12

Thirteen rounds of pointing the kit at a real 2426-source PowerBuilder
workspace and fixing what broke. Nineteen defects, each found by running
the flow rather than reading it, each fixed against the case that
exposed it. The rounds stopped when one of them found nothing new.

**Why a minor bump.** Several of these change what a review *does* — a
new resolution flavour, a different rule for where artefacts go, a
pruning step the old order did not have — so a project pinned to
v0.1.10 gets different behaviour, not just better wording.

**What this pass could not have found.** The workspace is one product
line: one vendor's conventions, one language, one PB release. The
sixteenth defect was still novel at round twelve, so the honest reading
of "a round found nothing" is *this* round found nothing, on the
mechanisms it exercised — not that the kit is clean.

### Corrected — the review flow

- **A plan file linked into a directory the consumer gitignores.** The
  plan goes into the reviewed project's repository; the installed bundle
  is harness state and does not. Together they produced a document whose
  catalog references resolve only on the machine that wrote it. Plan
  files now cite by slug plus public URL. The rule was also worded around
  `.claude/` in four places — it is about the bundle, not one assistant,
  and under `-Harness generic` the bundle is elsewhere.

- **The in-memory export was offered as a way to measure `.pbl`-vs-file
  drift.** It returns the object *body*: no export headers, and no binary
  section. On an `olecustomcontrol` the omitted tail was 8 196 bytes,
  **40% of the file**, so the comparison reports a mismatch that is not
  drift. `pb_object_export_file` to a scratch directory is the one that
  returns the whole file — verified byte-identical on an OLE-bearing
  window, binary tail included, despite `export_include_binary`
  defaulting to false at the session level.

- **A vendored target had nowhere honest to put its output.** Reviewing a
  shared framework from the project that consumes it is legitimate, but
  every finding is `outside_source_tree`, the apply loop refuses them all,
  and the flow would still have appended an `[Unreleased]` section to the
  consuming project's `CHANGELOG.md` listing fixes that will never be made
  there. The plan file is still written; the changelog entry is not, the
  handoff is not offered, and Pre-flight 0 records that the prior-review
  history it looks for lives in another repository.

- **The target list came from a filesystem glob.** `src/*.pbt` and the
  `.pbw` disagree in both directions: the glob missed targets in
  subdirectories and picked up two orphaned `.pbt` files no workspace
  declares. `pb_target_info` on the `.pbw` answers authoritatively in one
  sessionless call; the grep shortcut still applies, over the paths it
  returns.

- **Free-form intent had one sentence instead of a procedure.** It said to
  guess a naming pattern and enumerate libraries — which on this workspace
  found one DataWindow when asked for "the shipment tracking flow", while a
  content grep found sixteen entries across five libraries. The domain is
  spelled in the codebase's language and its vendors' names. Now Flavor D
  in `pb-context-build`, with the `pbl_only` fallback and the
  group-by-library presentation.

### Corrected — context building

- **The prerequisite table conflated "session open" with "current
  application set."** ORCA reports them separately (`-12` vs `-13`); the
  two query primitives need both. The table now has two columns and names
  the codes.

- **The library list is set once per session.** A second
  `pb_set_library_list` answers `PBORCA_DUPOPERATION (-2)`. The wording
  invites shrugging it off, and carrying on means every later query
  answers against the *previous* workspace — plausibly, with entries that
  resolve. Close the session and open again.

- **Neither ORCA size field is the size of the export.** `source_size` is
  UTF-16 code units, so halve it — verified on userobject, window, menu
  and datawindow. `object_size`, which is the only size a
  `pb_library_directory` listing carries and therefore what a library
  scope has to budget from, is unrelated: 2.7×–7.9× **over** for
  PowerScript entries and 0.58×–0.67× **under** for DataWindows. On one
  library the listing totalled 216 KB against 158 KB of real source, with
  the four DataWindows — 77% of the bytes — looking like a third.

- **The pruning order's first step is a no-op on non-visual objects.**
  "Drop `simple`-typed refs first" assumes a mix; a `nonvisualobject` has
  no `open` refs at all. Measured: 37 refs, all `simple`, depth-1 at 159%
  of the cap. Step (a′) ranks by inheritance/delegation membership then by
  size, and requires listing what was cut.

- **The grep shortcut for callers over-reports, and the caveat did not
  say how to stop it.** PowerBuilder names are compositional, so short
  names are infixes of long ones as a rule: `spedizione_anc` matched
  `regola_spedizione_anc`, which ORCA says references nothing. Anchoring
  with `\b` took the query from 5 files to 3. And grep does not know what
  a library is — one workspace had 20 entry names duplicated across
  libraries, `u_app` in thirteen.

- **`.pbd` libraries enumerate but cannot be read.**
  `pb_library_directory` lists their entries; every
  `pb_library_entry_export` and `pb_library_entry_information` on those
  same names answers `PBORCA_OBJNOTFOUND (-3)`, *"was not found"* — as if
  you had mistyped it. Refs into a compiled library are now recorded as
  present-but-unreadable.

- **`pb_library_export_sources` returns more than it saves.** One record
  per entry, each carrying the absolute path: 5.5 KB for 21 entries,
  extrapolating to ~84 KB for a 327-entry library — over half the source
  budget, in repeated paths. Take `count`/`skipped`/`failed` and go to
  the files.

### Corrected — the installer

- **The duplicate-ORCA-server warning never fired on the shapes that
  occur.** It matched the hyphenated package name inside a server's
  definition, missing both `-m pb_orca_mcp` (underscores, because that is
  the module name) and a stale entry keyed `pb-orca-mcp` whose value names
  nothing. Now folds `_` to `-` and inspects the key.

- **A config that could not be parsed was rewritten anyway.**
  `ConvertFrom-Json` accepts `{ "mcpServers": { "broken": , } }`, yielding
  `null`, so the documented guarantee rested on a parser too lenient to
  enforce it. `JsonDocument.Parse` validates first.

- **Nothing said the bundle directory wants gitignoring.** A
  `-Harness generic` install lands in `.agent/`, which that consumer's
  `.gitignore` did not cover, so the next `git add -A` would commit it.
  The installer now checks and prints the missing rule. That check was
  wrong on the first attempt: `git check-ignore -q -- '.agent/'` — with a
  trailing slash — returns 0 citing a **blank** `.gitignore` line, so the
  hint silently never fired.

### Added

- **`tests/test_installer_mcp_merge.py`** — runs the installer against
  planted configurations and asserts the duplicate warning fires, the
  unrelated servers survive, no false positive on a project that merely
  has other servers, and a malformed config is left untouched. It found
  the lenient-parser defect while being written for the other one.

- **Two antipattern catalog entries**, both from findings in these runs,
  both with a mechanical detection recipe:
  `pos-guarded-as-negative` (PowerScript's not-found sentinel is 0, never
  -1, so the `< 0` guard is dead and the code proceeds from an invented
  offset) and `halt-in-shared-library` (`MessageBox` and `HALT CLOSE` in a
  `.pbl` that headless targets also link). New *Process and control flow*
  category.

- **What to read in a DataWindow**, since the bug-risk list is entirely
  PowerScript and a `.srd` is not: `update=yes` on key columns, the
  `updatewhereclause` contract against what the framework does at runtime,
  raw SQL versus `PBSELECT`, retrieval arguments concatenated rather than
  bound, and `release N;` against the target's PB release.

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
