# Implementation spec: `pb-ai-code` Python CLI (phase 1: `install` + `status`)

Scope: replace `scripts/install-skills.ps1` with a Python console script distributed from GitHub and run from **inside** the consumer repo:

```
uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code install
```

The PowerShell script is the specification of record for behaviour. Roughly 25 of its lines exist because something went wrong once; the ledger below is the list of them. Anything marked **KEEP** must land byte-for-byte identical in effect. Anything marked **DIVERGE** is a deliberate change with a reason and a test.

---

## 1. The behaviour ledger

Format: `N. <contract-id>`: behaviour. **Port:** KEEP / KEEP+FIX / DIVERGE / DROP / NEW. **Risk:** as reported (highest rating wins where two agents disagreed). **Assert:** the observable that proves it.

### A. Source resolution and provenance

**1. `source-resolution-from-psscriptroot`**: every input is derived from `$source = <script>/..` (ps1:270-271, 293, 320-323, 377, 384, 480-482, 548). **Port: DIVERGE (mandatory).** Inputs come from the wheel payload at `pb_ai_code/_kit/`, resolved by `importlib.resources`, with a checkout fallback (§3). **Risk: high.** **Assert:** `uvx --from git+…@tag pb-ai-code install` into an empty dir installs the full bundle with no checkout on the machine.

**2. `source-must-be-a-git-checkout` / `exit-code-source-not-a-git-repo`**: three unguarded `git -C $source` calls (ps1:326-329); a non-repo source dies with `.Trim()` on `$null`, exit 1, before anything is copied. **Port: DIVERGE.** Git is optional. Provenance resolution order: (a) checkout detected → short sha + branch + dirty; (b) PEP 610 `direct_url.json` → VCS url + requested revision + commit; (c) distribution version alone. **Risk: high.** **Assert:** install from a wheel with no `.git` anywhere exits 0 and writes a well-formed `# Source:` line.

**3. `dirty-detection-counts-untracked`**: `git status --porcelain` non-blank, untracked files included (ps1:328-329). **Port: KEEP, narrowed** to checkout-mode installs only (a uvx install from a tag can never be dirty). **Risk: high.** **Assert:** one untracked, non-ignored file in the checkout raises both the stdout WARN and the marker WARN.

**4. `dirty-warning-on-stdout`**: `WARN: source repo has uncommitted changes; the install may include unversioned work.` on stdout, immediately after the `Source:` line, present tense (ps1:332-336). **Port: KEEP verbatim.** **Risk: medium.** **Assert:** exact string, exactly once, as the line after `Source:`.

**5. `marker-dirty-warn-line`**, ninth marker line, past tense: `# WARN: source repo had uncommitted changes at install time.` (ps1:566-568). **Port: KEEP verbatim.** **Risk: high.** **Assert:** absent on a clean source; present and positioned after `# Appeon:` on a dirty one. Two different strings, do not unify them.

### B. Parameters, preconditions, refusals

**6. `param-set-and-binding`**: six parameters; `Target` positional; `Harness` validated set, case-insensitive, default `generic`. **Port: KEEP shape, DIVERGE on case.** `--harness` is normalised with `type=str.lower`; the marker records the normalised spelling, not the user's. **Risk: medium.** **Assert:** `--harness CLAUDE-CODE` succeeds; marker says `claude-code`; unknown value exits 2 naming the legal set.

**7. `missing-target-means-self-install`**: absent/blank `-Target` = install into the source (ps1:273-283). **Port: DIVERGE.** `--target` defaults to **cwd**. The self-install concept disappears (§4). **Risk: high.** **Assert:** run with no `--target` inside a scratch dir → the bundle lands there.

**8. Target must be an existing directory; it is never created** (ps1:278-279, `Target is not a directory: <path>`). **Port: KEEP.** **Risk: medium.** **Assert:** non-existent `--target` exits 2, one-line stderr message, nothing written.

**9. `harness-claude-code-layout`**, five fixed destinations: `.claude/skills`, `.claude/commands`, `.claude/settings.json`, `.mcp.json`, `.claude/_installed-from-pb-ai-code.txt` (ps1:290-297). `--skills-dir`/`--commands-dir` are ignored for this harness. **Port: KEEP, DIVERGE on silence**, passing them with `claude-code` now exits 2 rather than being silently ignored. **Risk: low.** **Assert:** exactly those six paths exist after an install and nothing else at the target root.

**10. `generic-default-directories`**: `-Harness generic` without directory flags uses `.agents\skills` and `.agents\commands`. **Port: CHANGE**, with explicit paths still validated as target-relative sibling directories. **Risk: medium.**

**11. `skillsdir-absolute-is-documented-but-broken`**: help says absolute is allowed (ps1:68-72); `Join-Path` produces `C:\tgt\D:\abs\skills`. **Port: KEEP+FIX → refuse.** `--skills-dir` / `--commands-dir` must be target-relative; absolute paths, drive-qualified paths and any value that resolves outside the target exit 2. **Risk: high** (Python's `Path` join would silently "fix" this into installing outside the target). **Assert:** `--skills-dir C:\tmp\x` exits 2; `--skills-dir ../../x` exits 2.

**12. `commandsdir-defaults-under-agents`**: generic installs use `.agents\commands` when no commands directory is supplied; explicit command paths remain optional for clients that do not consume the wrappers. **Port: CHANGE.** **Risk: low.**

**13. `skillsdir-commandsdir-overrides`**: `--skills-dir` drives four derived paths (skills dest, docs dest, marker, gitignore bundle root); forward and back slashes both accepted. **Port: KEEP.** **Risk: medium.**

**14. `validate-everything-before-writing`**: the whole plan is built and every source existence-checked before the first copy, deliberately so `--dry-run` catches it too (ps1:353-400, comment at 396-397). **Port: KEEP.** **Risk: medium.** **Assert:** remove any payload input → exit non-zero with a fresh target still empty, in both normal and dry-run mode.

### C. What is copied, and where

**15. `install-every-skill-whole-directory`**: every immediate subdirectory of `skills/`, copied as a **whole tree** (`Copy-Item -Recurse`), never as a bare `SKILL.md`; sorted alphabetically. The set contained 7 skills when this port was specified and is discovered at runtime. **Port: KEEP.** **Risk: medium.** **Assert:** a planted `skills/pb-review/references/x.md` appears at `<bundle>/skills/pb-review/references/x.md`. Rationale: commit e04a11d deleted the `-Bundle review` subset because 7 dead cross-links resulted; 59 `../<skill>/SKILL.md` links exist today.

**16. `contents-are-enumerated-not-listed`**, the set is a glob at run time, not a list in code (ps1:318-323). **Port: KEEP.** Python must `sorted(..., key=str.lower)` explicitly, `iterdir()` order is not guaranteed and the plan order is the marker's Contents order. **Risk: low.**

**17. `copy-commands-flat-md-only`**: `commands/*.md`, flat, non-recursive, individual files, plain overwrite with **no pre-delete** (ps1:322-323, 362-375). **Port: KEEP.** **Risk: low.** **Assert:** a pre-existing unrelated `my-command.md` in the commands directory survives a re-install.

**18. `doc-trees-vendored-as-pb-ai-code-docs`**: `docs/pb-antipatterns/` and `docs/pb-source-format/` copied whole (ps1:118, 376-382). Mandatory as a pair. **Port: KEEP.** **Risk: low.**

**19. `loose-doc-files-copied-too`**, `docs/wiki-notes.md` copied as a loose file into the docs **root**, not into a tree (ps1:120-125, 383-389). **Port: KEEP.** **Risk: high.** Rationale: commit 308ff22 / CHANGELOG 0.1.6, omitting it produced exactly 5 dead links. **Assert:** delete the docfile step and the installed-layout link test reports exactly 5 dead links.

**20. `docs-folder-name-and-parent-placement`**: docs land at `parent(skills_rel)/pb-ai-code-docs/`; bare `pb-ai-code-docs` when the skills dir has no parent (ps1:126, 309-316). The name is deliberately not `docs/` (would collide with the host project's own). **Port: KEEP.** **Risk: high.** **Assert:** `--skills-dir a/b/skills` → docs at `a/b/pb-ai-code-docs/`; the installed `pb-antipatterns/index.md → ../../skills/pb-review/SKILL.md` resolves with no rewrite applied to that file.

**21. `docs-deliberately-not-copied`**: the copy set is closed. `docs/install.md`, `docs/appeon-index/` (incl. `index.db`), `plan-self-bootstrap.md`, `harness/README.md`, root `README/AGENTS/CHANGELOG/PLAN/LICENSE`, `tools/`, `tests/`, `scripts/` never reach a target. **Port: KEEP.** **Risk: medium.** **Assert:** no `install.md`, no `*.db`, no `appeon-index/` and no installer copy anywhere under the target.

**22. `settings-json-full-overwrite`**, `harness/claude-code/settings.json` copied verbatim over `<target>/.claude/settings.json`, no merge, no backup, no warning; claude-code only; missing source throws (ps1:390-395, 438-440). `.claude/settings.local.json` is never touched. **Port: KEEP behaviour, ADD observability**, one stdout line and one marker line when an existing file was replaced and differed. **Risk: high** (rated medium by one agent, high by another; treat as high: it is the single most destructive undocumented behaviour). **Assert:** a target `settings.json` with unrelated keys is byte-identical to the canonical file after install; `--harness generic` writes no settings file.

**23. `settings-json-contents`**, the file pre-approves 18 tools (14 `mcp__pb-orca__*`, 4 `mcp__pb-appeon-index__*`), sets `enabledMcpjsonServers`, and carries three `_comment*` keys documenting the deliberate omissions (`pb_object_export_file`, `pb_object_import_file`, `pb_object_regenerate`). The allow-strings embed the server key `pb-orca`. **Port: KEEP as an opaque byte copy**, never parse or re-serialise it. **Risk: medium.** **Assert:** installed file is byte-identical; `_comment*` keys survive.

**24. `delete-before-copy-for-trees`**, for `skill` and `docs` rows only: `Remove-Item -Recurse -Force` then copy; single-file rows are plain overwrites (ps1:427-440). Two reasons, both verified: PowerShell's recursive copy into an existing directory *nests* (`dst/tree/tree/…`), and a fresh slate is what makes an upstream deletion propagate. **Port: KEEP.** **Risk: high.** **Do not use `shutil.copytree(dirs_exist_ok=True)`** because it dodges the nesting bug and silently reintroduces the staleness bug. **Assert:** plant `<bundle>/pb-ai-code-docs/pb-antipatterns/ghost.md` and edit an installed `SKILL.md`; after re-install both are gone and no doubled path exists.

**25. NEW: read-only destinations.** `Remove-Item -Force` deletes read-only files and `Copy-Item -Force` overwrites them; `shutil.rmtree` / `copyfile` raise `PermissionError`. **Port: NEW code.** `rmtree(onexc=…)` clearing `stat.S_IWRITE` and retrying; before overwriting a single file, clear the read-only bit if the destination exists. **Risk: high** (a target checked out read-only, or a bundle someone committed, breaks the port where the script worked). **Assert:** install into a target whose `.claude/skills/pb-review/SKILL.md` is read-only → exit 0, file replaced.

**26. `no-pruning-of-the-bundle` / `install-is-additive-never-prunes`**: deletion is scoped to the destinations about to be written. A stale skill, a stale doc tree, a user's own skill, a loose user file at the docs root and a user command all **survive** a re-install (verified, five shapes). **Port: KEEP.** **Risk: medium.** **Assert:** planted `skills/pb-obsolete/` and `skills/my-own-skill/` both survive and neither appears in the marker's Contents.

**27. `copies-are-byte-exact`**, no newline translation, re-encoding, or BOM
introduction. A developer checkout can retain CRLF files from before its LF
attributes took effect, so a local payload is not allowed to change those
bytes during installation. **Port: KEEP, binary copies only**
(`shutil.copy2`); the rewrite reads and writes **bytes**. **Risk: high.**
**Assert:** every installed file is byte-identical to its payload source
except rewritten `SKILL.md` files, which differ only by the substitution.

### D. The link rewrite

**28. `knowledge-base-link-rewrite` / `link-rewrite-scope`**, after copying, `../../docs/` → `../../pb-ai-code-docs/`, ordinal, case-sensitive, all occurrences, literal (not regex, not link-aware, rewrites inside fenced code blocks too), applied to `<skills>/<name>/SKILL.md` **only**, not nested skill files, not commands, not the doc trees, not `wiki-notes.md` (ps1:444-462). Write back only if changed; count and report. In the current payload N=5 of 8, with 28 occurrences (pb-src-format 13, pb-review 8, pb-format 3, pb-scaffold 3, pb-apply-plan 1). **Port: KEEP.** **Risk: high.** **Assert:** stdout `Rewrote knowledge-base links in 5 skill file(s).`; zero `../../docs/` anywhere under the installed bundle; 13 occurrences of the new prefix in `pb-src-format/SKILL.md`.

**29. `self-install-copies-docs-identically`**: the rewrite and the docs copy are **unconditional**; the comments at ps1:115-117 and 26-31 claiming otherwise are stale and were recanted in the very commit that wrote them (e04a11d). **Port: KEEP unconditional.** A port that reads the comments and writes `if not self_install: copy_docs()` fails exactly here. **Risk: high.** **Assert:** run inside the pb-ai-code checkout with no `--target` → `.claude/pb-ai-code-docs/` exists and the installed skills carry the rewritten prefix.

**30. `nothing-else-is-rewritten`**: commands link `../skills/<name>/SKILL.md` (2 occurrences) and this resolves only because commands and skills are siblings. `--skills-dir agents/skills --commands-dir prompts` produces two dead links; the script neither validates nor rewrites. **Port: KEEP+FIX → refuse.** The port rejects a `--commands-dir` that is not a sibling of `--skills-dir` (exit 2). **Risk: medium.** **Assert:** the non-sibling combination exits 2 with a message naming the invariant.

### E. MCP configuration

**31. `single-canonical-source`**: servers come from `harness/mcp-servers.json` only; missing file → `MCP server config missing: <path>`; missing `mcpServers` key → `<path> has no 'mcpServers' key.`; only the value of `mcpServers` is returned; the owned-key set is data, not code (ps1:133-151). **Port: KEEP**, reading the file from the packaged payload. **Risk: low.** **Assert:** adding a second key to the file makes it appear in the target and in the outcome list with no code change; `tests/test_pins_in_sync.py:93-121` must keep passing.

**32. `preflight-vs-late-read`**: existence checked early (in the plan, so `--dry-run` catches it), read late (ps1:396-400, 468). **Port: KEEP.** **Risk: medium.**

**33. `skip-mcp-still-requires-the-source-file`**: latent bug: with `-SkipMcpConfig` the preflight is skipped but `Get-McpServerBlock` still runs at 468, so a missing file aborts **after** everything is copied and **before** the marker is written. **Port: KEEP+FIX.** Load lazily; `--skip-mcp-config` must not need the file. **Risk: medium.** **Assert:** delete the payload file, run with `--skip-mcp-config` → exit 0 and a marker exists.

**34. `merge-preserves-everything`**: the whole target document is rewritten but every top-level key, every unowned server, and both insertion orders are preserved; owned keys are replaced in place, new owned keys appended (ps1:170-204, 217, 256-265). **Port: KEEP.** Use `json.load(..., object_pairs_hook=dict)` (3.7+ dicts are ordered) and write the full document back. **Risk: high.** **Assert:** plant `{"someTopLevelKey":…,"mcpServers":{"postgres":…}}` → the sibling key keeps its value *and* its position ahead of `mcpServers`; `postgres` stays first. Untested today.

**35. `server-key-matching-is-case-insensitive`**, PowerShell's ordered dictionaries are case-insensitive, so an existing `PB-Orca` is **updated**, not joined by a second `pb-orca` (verified end to end). A Python dict does the opposite and manufactures the exact fault the duplicate warning exists to catch. **Port: KEEP, made explicit, with one divergence**, match owned keys by casefold, and rewrite the key to the canonical spelling `pb-orca`, because `harness/claude-code/settings.json` hard-codes `mcp__pb-orca__*` and a differently-cased key silently loses every permission allowance. **Risk: high.** **Assert:** plant `{"mcpServers":{"PB-Orca":{…},"keepme":{…}}}` → exactly one ORCA key, spelled `pb-orca`, in the original position, reported `pb-orca (updated); kept: keepme`.

**36. `strict-json-validation`**, the target file is validated strictly *before* parsing; anything that fails is left **byte-for-byte untouched**, the block is printed for a hand merge, the run continues and exits 0 (ps1:174-196, 517-520). The strict step rejects trailing commas, `//` and `/* */` comments and `NaN`. **Port: KEEP.** `json.loads` matches on comments/trailing commas but **accepts** `NaN`/`Infinity`, pass `parse_constant=` that raises. **Risk: high.** Rationale: CHANGELOG 0.2.0 / commit 5e16e6c: `{ "mcpServers": { "broken": , } }` was being rewritten with the user's half-typed value coerced away. **Assert:** `tests/test_installer_mcp_merge.py::test_malformed_config_is_left_alone` ported verbatim, plus new cases for trailing comma, comment, `NaN`.

**37. `empty-file-is-not-a-parse-failure`**, whitespace-only content short-circuits to `{}` *ahead* of the strict parse; a missing file and `{"mcpServers": null}` behave the same (ps1:171-176, 200-202). **Port: KEEP.** **Risk: high.** **Assert:** three cases, no file, zero-byte file, `{"mcpServers":null}`: all produce a written config, never a `not valid JSON` warning. None is tested today.

**38. NEW: BOM.** `Get-Content -Raw` strips a UTF-8 BOM, so a BOM'd `.mcp.json` merges cleanly today. `open(encoding="utf-8")` would see `\ufeff`, fail, and take the refuse-to-write path on a perfectly good file. **Port: read with `utf-8-sig`, write without a BOM.** **Risk: high.** **Assert:** a BOM'd valid `.mcp.json` merges and comes back BOM-free.

**39. `mcpservers-non-object-is-destroyed`**, `{"mcpServers":"oops"}` parses, iterates nothing, and is overwritten; sibling keys survive. **Port: KEEP+FIX → route to the untouched-and-print path**, since it is the one route by which a *parseable* file loses data, precisely what the strict-parse work defends against. **Risk: low.** **Assert:** `{"mcpServers":"oops","other":1}` is left byte-identical and the block is printed.

**40. `outcome-vocabulary`**: one token per owned key in `$Servers.Keys` order: `<name> (added)` / `(updated)` / `(already current)`, plus a single trailing `kept: a, b` (merged order, omitted when empty), joined with `'; '` into one stdout line and one marker line (ps1:206-222, 517-524, 563). **Port: KEEP verbatim.** **Risk: high.** **Assert:** first run `(added)`, second `(already current)`, planted old pin `(updated)`, unrelated server → trailing `kept: postgres`. No test asserts any of these four strings today.

**41. `already-current-is-string-equality`**: compressed-JSON *string* comparison, so a key-reordered but identical server reports `(updated)` (ps1:210-212). The file is rewritten either way; the comparison only picks a word. **Port: DIVERGE → dict equality.** `existing == incoming` reports `already current` for a reordered server, which is the honest answer. **Risk: medium.** **Assert:** hand-reorder the keys inside the written `pb-orca` object, re-install → `already current`. Pin it with a test; it is untested today either way.

**42. `duplicate-orca-detection`**, every *preserved* (unowned) server is scanned; blob = compact JSON of the value **plus the key**, with `_` folded to `-` on both sides; matched against the literal list `@('pb-orca-mcp')`, case-insensitively, as a plain substring; a guard checks our own block still names the package (ps1:224-254). Fires on a bare path component (`C:/tools/pb_orca_mcp/venv/python.exe`). Prints five yellow lines wrapped in blanks, ending `Left in place - it is your file. Remove '<name>' unless you meant to keep it.` **Never removes anything**, does not change the outcome list, does not change the exit code. **Port: KEEP verbatim,** including the case-insensitive match and the self-check. **Risk: high.** Rationale: commit 0d9035c, found by installing into rstpb22, which had carried two ORCA servers since May; ORCA is single-session per process and only one key prefix matches the allowlist.

**43. `underscore-folding-and-key-inspection`**, the two specific edits that made the warning fire on the shapes that occur: append the key to the blob, fold `_`→`-` on both sides (ps1:240-244). **Port: KEEP.** **Risk: high.** Rationale: CHANGELOG 0.2.0, "A warning that silently stops firing is worse than no warning." **Assert:** the two parametrised cases at `tests/test_installer_mcp_merge.py:63-68` are the contract test; port them unchanged.

**44. `duplicate-check-covers-orca-only`**: the scanned list is literally `@('pb-orca-mcp')`; a duplicate of `pb-appeon-index` is preserved silently (the list predates the second server). **Port: DIVERGE → extend to `("pb-orca-mcp", "pb-appeon-index")`.** The loop shape already supports it; the allowlist argument applies to both. **Risk: low.** **Assert:** a server whose value contains `pb_appeon_index` under any key now warns.

**45. `owned-key-is-clobbered-silently`**: a foreign server sitting on one of our keys is replaced with no warning; only `(updated)` shows. The duplicate scan cannot fire because it walks `kept` only. **Port: KEEP.** **Risk: low.** Note the asymmetry in the docs: a copy under a *different* key earns five lines and survives; a foreign server under *our* key is destroyed in silence.

**46. `write-mechanics`**, 2-space indent, CRLF, UTF-8 no BOM,
trailing newline, arrays exploded one element per line, parent directory
created on demand, serializer depth capped at 10 (ps1:258-265). The depth
cap silently truncates a deeply nested preserved server to a type-name
string. **Port: DROP the depth cap and preserve an existing project's newline
style.** New files use CRLF; an LF file stays LF after the merge. Output is
UTF-8 without BOM with one trailing newline. **Risk: medium.** **Assert:**
byte-check new and existing `.mcp.json` files; plant a 12-level-deep unrelated
server and assert it survives semantically.

**47. `generic-harness-writes-neutral-mcp`**: generic installs write the neutral JSON block to `<target>/.agents/mcp.json`; existing keys are preserved and the marker records the merged path. **Port: CHANGE.** Native Codex, OpenCode and other client dialects remain outside this adapter; translate the neutral block when needed. **Risk: medium.** **Assert:** `--harness generic --skills-dir .agents/skills` writes `.agents/mcp.json` and records it in the marker.

**48. `skip-mcp-config`**: five gates: preflight, plan line (`mcp       skipped (-SkipMcpConfig)`), the merge (prints `Skipped MCP config (-SkipMcpConfig). The skills expect the pb_* tools to be reachable.`, outcome `skipped (-SkipMcpConfig)`), the whole Appeon report, the `/mcp` restart hint, and the MCP line in the gitignore hint (ps1:398, 408-410, 511-514, 538, 594, 630). **Port: KEEP**, with the flag renamed `--skip-mcp-config` and the plan/outcome strings updated to that spelling. **Risk: high.** **Assert:** an existing selected MCP file is byte-identical afterwards; the four suppressions hold.

### F. The Appeon index

**49. `appeon-three-way-presence-check`**, `<source>/.venv/Scripts/python.exe`, `<source>/docs/appeon-index/index.db`, `<source>/tools/pb-appeon-index/src/pb_appeon_index`; all three present → an owned `pb-appeon-index` key with absolute paths and `env.PB_APPEON_INDEX_DB`; otherwise `$missing` in the fixed order *database, interpreter, module* (ps1:470-508). **Port: DIVERGE (mandatory, the checkout does not exist).** Replace with a **database-only** probe, resolved in order: `PB_APPEON_INDEX_DB` env var → `~/.pb-appeon-index/index.db` → `<checkout>/docs/appeon-index/index.db` when running from a checkout. When a DB is found, write:
```json
"pb-appeon-index": {
  "command": "uvx",
  "args": ["--from", "git+https://github.com/restoresrl/pb-ai-code",
           "pb-appeon-index", "serve-mcp"],
  "env": {"PB_APPEON_INDEX_DB": "<abs db>"}
}
```
`<version>` comes from the running distribution (§3). When no DB is found, the note becomes `pb-appeon-index NOT configured - missing the index database`. **Risk: high.** **Assert:** with a DB present the server is written and points at it; with none, the note and the build recipe print and no key is written.

**50. `appeon-database-is-referenced-not-copied`**: the DB is pointed at, never copied; one file serves every project (ps1:481, 489-497; CHANGELOG 0.4.0 "N stale copies instead of one live file"). **Port: KEEP.** **Risk: medium.** **Assert:** no `.db` anywhere under the target.

**51. `appeon-reported-on-both-branches`**, success: `Appeon index      <db>` plus `                  referenced, not copied - rebuilding it once updates every project`; failure: blank line, `Note: <note>`, then the degradation sentence and the build recipe (ps1:537-553). The same note goes into the marker on both branches. **Port: KEEP the shape, REWRITE the recipe**, `cd <source>` no longer exists (§8, verification item 4). **Risk: medium.** Rationale: CHANGELOG 0.4.0: "the failure is silent by nature. A missing server is not an error anywhere."

**52. `stale-appeon-entry-survives`**, with the index absent, an entry from an earlier install falls into `kept` and is written back untouched, while the installer simultaneously reports the server NOT configured, possibly pointing at a checkout that no longer exists. **Port: KEEP the preservation, FIX the report.** When an unowned `pb-appeon-index` key is present and we could not configure one, the note becomes `pb-appeon-index NOT configured here - the target's existing entry was left in place`. **Risk: medium.**

**53. `appeon` computed vs written**: the note reports what was *computed*, not what was *written*: with `--skip-mcp-config` or an unparseable target file the marker still says `configured`. **Port: KEEP+FIX.** The marker's `# Appeon:` line reports the outcome; under `--skip-mcp-config` it reads `not evaluated (--skip-mcp-config)`. **Risk: medium.**

### G. The marker file

**54. `marker-path-per-harness`**, `.claude/_installed-from-pb-ai-code.txt` for claude-code (beside the skills), `<SkillsDir>/_installed-from-pb-ai-code.txt` for generic (**inside** the skills directory) (ps1:296, 304). Both `skills/pb-review/SKILL.md:771-773` and `docs/wiki-notes.md:77` tell the reader it is in the bundle directory, which the generic branch contradicts. **Port: DIVERGE → one rule: `parent(skills_rel)/_installed-from-pb-ai-code.txt`.** For claude-code this is byte-identical to today; for generic it moves to the bundle root, which is what both consuming documents already promise, and it stops a stray `.txt` sitting where a skill loader enumerates skills. **Risk: medium.** **Assert:** claude-code marker at `.claude/…` unchanged; `--skills-dir .agents/skills` → `.agents/_installed-from-pb-ai-code.txt`.

**55. `marker-fixed-header-and-key-alignment`**: `#`-comment file, values aligned at column 14, all ASCII, hyphens never em dashes (ps1:555-565). **Port: KEEP the alignment and the ASCII rule.** **Risk: medium.**

**56. `marker-installed-timestamp`**, `# Installed: yyyy-MM-dd HH:mm:ss zzz` → `2026-08-12 17:02:56 +02:00`: local time, space between date and time, colon in the offset (ps1:330, 560). **Port: KEEP.** Python's `%z` gives `+0200`, insert the colon, or use `datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")` and splice. **Risk: medium.** **Assert:** matches `^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{2}:\d{2}$`.

**57. `marker-source-line-is-the-only-consumed-line`**: `# Source:    pb-ai-code @ <short-sha> (<branch>)` is read by hand by `skills/pb-review/SKILL.md:721, 812-818` (plan header `source skill` field) and `docs/wiki-notes.md:76-80` (`observed-against`), and "n/d" is explicitly forbidden. **Port: DIVERGE, coordinated.** New shape, preserving the `pb-ai-code @ ` prefix:
```
# Version:   0.5.0
# Source:    pb-ai-code @ 0.5.0 (git+https://github.com/restoresrl/pb-ai-code, c26d4b6)
# Source:    pb-ai-code @ 0.5.1.dev1+gc26d4b6 (local checkout C:\...\pb-ai-code, c26d4b6 on main)
```
`# Version:` is the machine-readable single token. **`skills/pb-review/SKILL.md` and `docs/wiki-notes.md` must change in the same commit**: a tag is strictly better than a sha for `observed-against`. **Risk: high.**

**58. `marker-mcp-line-four-values`**: exactly four shapes, note the **two spaces** before `[` (ps1:510-535, 563). **Port: KEEP** (with the renamed flag string). **Risk: medium.**

**59. `marker-contents-list`**: `#` + three spaces + the destination relative to the target, backslash-separated on Windows, in plan order; trees listed as directories; `.mcp.json`, the marker itself and per-file contents are **not** listed (ps1:569-572). **Port: KEEP.** **Risk: medium.**

**60. `marker-snapshot-and-update-footer`**: the SNAPSHOT paragraph plus `# Source of truth: …` and the `To update:` recipe (ps1:573-585). **Port: KEEP the snapshot block verbatim; REWRITE the recipe:**
```
# To update: from inside this project, run
#   uvx --from git+https://github.com/restoresrl/pb-ai-code pb-ai-code install
```
Use the recorded release tag; for a development build, print the command without a ref plus `# (installed from a development build; pin a tag for a real install)`. **Risk: high**: a port that copies the block unchanged ships an instruction that no longer works.

**61. `marker-bytes-utf8-nobom-crlf`**: UTF-8 **without BOM**, CRLF throughout including the trailing newline (ps1:555, 590). **Port: KEEP on every platform** (parity beats platform-nativeness here; the marker is a generated file inside a gitignored bundle). **Risk: high.** **Assert:** no `\xef\xbb\xbf`, contains `\r\n`, no bare `\n`, ends with exactly one `\r\n`, decodes as ASCII.

**62. `marker-written-last-non-atomically` / `failure-mode-partial-target-no-marker`**, the marker is the last write; any failure before it leaves a populated target with a stale, confidently wrong marker or none at all. **Port: KEEP the ordering, ADD atomicity**, write to a temp file in the same directory and `os.replace`. **Risk: low→medium.**

**63. `marker-omissions-that-block-self-update`**, no tag, no remote, no pins, no per-file inventory, no hashes, no flags beyond harness, no machine-readable form. **Port: partially addressed**, `# Version:` lands now (57); the inventory and hashes are deferred (§7).

### H. stdout, exit codes, the gitignore hint

**64. `stdout-line-order`**, a fixed 20-step sequence; everything is `Write-Host`, i.e. stdout; stderr is empty on success; colours vanish when redirected. **Port: KEEP the order and the single-stream rule** (§4). **Risk: high.** Not stated as a contract anywhere today, pin it with goldens.

**65. `stdout-plan-table-format`**: `"{op,-9} {src} -> {dst}"` with the source and target roots textually replaced by `<src>` / `<dst>`; ops `skill|command|docs|docfile|settings`; three pseudo-rows `mcp`, `marker`, `rewrite`; two spaces before `(merged; other servers preserved)` and before `in the installed skills` (ps1:402-419). **Port: KEEP.** **Risk: medium.**

**66. `stdout-apply-and-rewrite-lines`**: `Installed {op,-9} {leaf}` per row (leaf only), then the rewrite count line; the MCP row uses `Installed {op,-9} {rel}  [{outcomes}]` with two spaces (ps1:441, 462, 522). **Port: KEEP.** **Risk: low.**

**67. `stdout-mcp-warning-blocks`**: both warnings print from inside the merge, before the `Installed mcp` line, each wrapped in blank lines, on **stdout**. Existing tests assert the literal substrings `competing for a single-session ORCA library` and `not valid JSON`. **Port: KEEP.** **Risk: medium.**

**68. `stdout-tail-done-and-restart`**: blank line, `Done.`, then the restart line for claude-code without `--skip-mcp-config`; the gitignore note prints **after** `Done.`, so `Done.` is not the last line. **Port: KEEP.** **Risk: low.**

**69. `gitignore-hint-check-form`**: `git check-ignore -q -- <bundleRoot>` with **no trailing slash**, run from inside the target, **after** the copy (ps1:598-634). The no-slash form is only correct because the directory now exists. **Port: KEEP, run `git -C <target>`** rather than changing process CWD. **Risk: high.**

**70. `gitignore-hint-trailing-slash-bug`**, the recorded bug: `git check-ignore -q -- '.agents/'` matches a **blank line** in a CRLF `.gitignore` and reports the path ignored, so the hint silently never fired (commit 2a365a7, reproduced on git 2.40.1). CRLF `.gitignore` files are the norm on the Windows PB repos this kit targets. **Port: KEEP the corrected form.** **Risk: high.** **Assert:** regression test, a git repo whose `.gitignore` is CRLF with a blank line and no rule for the bundle must still print `is not ignored`.

**71. `gitignore-hint-output-text`**: five or six lines, only the `Note:` line coloured, continuation indented 6, suggested rules indented 8, and the suggested rule printed **with** a trailing slash (`.claude/`) while the check queries without one; the `.mcp.json` line only for claude-code without `--skip-mcp-config` (ps1:624-633). **Port: KEEP verbatim.** **Risk: medium.**

**72. `gitignore-hint-gating`**: skipped on self-install, on dry-run, and silently when the target is not a git repo; the whole block is `try/catch`, so a missing `git` here is silent (unlike ps1:326, where it kills the run). **Port: KEEP** minus self-install (which no longer exists); a missing `git` executable stays silent here. **Risk: medium.** **Assert:** install into a non-git temp dir → exit 0, no `not ignored by git` text.

**73. `gitignore-hint-parent-repo-trap`**: the repo test answers true for a plain directory nested in an enclosing repository, so the advice is about the parent's `.gitignore` while the text says "in this project". **Port: KEEP+FIX.** Compare `git -C <target> rev-parse --show-toplevel` against the target; when they differ, say so in the note. **Risk: low.**

**74. `exit-codes`**, 0 on every path that reaches the end (including all warning paths and dry-run); 1 from an unhandled error, with a multi-line coloured banner on stderr; parameter binding errors also 1. Warnings never change the code. **Port: KEEP the "warnings exit 0" rule; DIVERGE on the taxonomy**, 0 success, 2 usage error (one stderr line, no traceback), 1 unexpected (traceback preserved). **Risk: high.** **Assert:** table test over every invocation.

**75. `dryrun-prints-plan-writes-nothing`**, validates every source, prints the full plan including the `rewrite` pseudo-row, prints `DryRun mode. No changes written.` and returns before the rewrite, the MCP block load, the Appeon probe and the merge. `Write-McpConfig`'s `-WhatIfOnly` switch is dead code. **Port: KEEP the "writes nothing" guarantee, WIDEN the report**, `--dry-run` also runs the Appeon probe and prints what the merge *would* do (`would add` / `would update` / `would leave`), because today's dry run is silent about exactly the two decisions a user wants previewed. The target file must remain byte-identical. **Risk: low.** **Assert:** `os.listdir(target) == []` after a dry run into an empty directory.

**76. `windows-and-pwsh7-assumptions`**, backslash literals throughout, `.venv\Scripts\python.exe`, two APIs Windows PowerShell 5.1 lacks, output bytes that depend on the host shell. **Port: DIVERGE**, pure `pathlib`, no shell dependency, no pwsh. Cross-platform *capability* follows; cross-platform *support* is not claimed this phase (§7). **Risk: high.**

**77. NEW: `status` verb.** Not present in the PowerShell script. **Port: NEW** (§4).

---

## 2. `pyproject.toml`: exact changes

Current file is 113 lines; the line numbers below are from that file.

**2.1, line 2, build backend.** `requires = ["hatchling>=1.18", "hatch-vcs>=0.4"]`
*Reason:* version identity. `pyproject.toml:7` says `0.1.10` while `git tag` reaches `v0.4.0`, three minors stale. Today that number is invisible; the moment the CLI stamps a marker from `importlib.metadata`, it is the number every consumer reads and the number `To update:` prints. Verified through the uvx path: at tag `v0.5.0` the distribution reports `0.5.0`; one commit past, `0.5.1.dev1+gc26d4b6e3`: a build that says out loud it is not a release.

**2.2: line 7.** Delete `version = "0.1.10"`. Add to `[project]`: `dynamic = ["version"]`. Add a new table:
```toml
[tool.hatch.version]
source = "vcs"
```

**2.3: `.github/workflows/ci.yml:22` and `:44`** (not pyproject, but same change): `uses: actions/checkout@v7` gains
```yaml
        with:
          fetch-depth: 0
```
*Reason:* verified trap: a shallow, tagless clone silently produces `0.1.dev1+g<sha>` with only a `UserWarning`, so CI would build mis-versioned wheels and never say so. `actions/checkout` defaults to depth 1.

**2.4, lines 53-55, scripts.** Add `pb-ai-code = "pb_ai_code.__main__:main"`.
*Reason:* hyphenated script = distribution name, pointing at `<underscored>.__main__:main`, the house pattern of the two existing entries.

**2.5: lines 61-65, wheel packages.** Add `"tools/pb-ai-code/src/pb_ai_code"`.
*Reason:* without it, CI's `pip install -e ".[dev]"` does not expose the module, the new tests fail at import, and the wheel `uvx` builds has no CLI.

**2.6: NEW table, the load-bearing one.**
```toml
# The kit itself travels in the wheel, under the package that installs it.
# force-include is the only mechanism that reaches a `uvx --from git+...`
# build (sdist `include` does not affect the wheel).
#
# Map these six paths and NEVER the docs/ root. force-include ignores
# .gitignore AND ignores `exclude` (both verified): mapping "docs" pulls
# docs/appeon-index/index.db into the wheel from any developer machine that
# has built it — 190 KB becomes 4.8 MB, and the DB is never redistributed.
[tool.hatch.build.targets.wheel.force-include]
"skills"                = "pb_ai_code/_kit/skills"
"commands"              = "pb_ai_code/_kit/commands"
"harness"               = "pb_ai_code/_kit/harness"
"docs/pb-antipatterns"  = "pb_ai_code/_kit/docs/pb-antipatterns"
"docs/pb-source-format" = "pb_ai_code/_kit/docs/pb-source-format"
"docs/wiki-notes.md"    = "pb_ai_code/_kit/docs/wiki-notes.md"
```
*Reason:* verified, a wheel built from a clean clone of HEAD today contains 18 entries and **not one file** the installer needs. With these mappings the payload is 37 files, exactly equal to `git ls-files skills commands harness docs/pb-antipatterns docs/pb-source-format docs/wiki-notes.md`. Whole directories, not file lists, because the installer discovers its inputs by glob (ps1:320, 322), a new skill must ship with no build change.

**2.7: lines 67-83, sdist include.** Add `"tools/pb-ai-code"`.

**2.8: lines 87-91, testpaths.** Add `"tools/pb-ai-code/tests"`.

**2.9: lines 100-103, `[tool.ruff] src`.** Add `"tools/pb-ai-code/src"`.
*Reason:* isort first-party classification; without it the new tests raise `I001` under `ruff check .`.

**2.10: line 112, `mypy_path`.** Append `:tools/pb-ai-code/src`. Colon separator resolves on Windows here because the paths are relative.

**2.11, line 30, `chardet>=5.2`.** Delete. Verified: it is imported nowhere in the repository, one hit, in `pyproject.toml` itself. Independent of everything else; free weight in every install.

**Not changed this phase:** the dependency list is not split into a `tools` extra. It would take the installer's cold start from 38 packages / 11.5 s to 1 package / 5.2 s, but it forces `--from "pb-ai-code[tools] @ git+…@tag"` everywhere the two tool scripts are invoked, including the `pb-appeon-index` server entry this CLI now writes, and risks orphaning the `mcp>=1.0,<2` ceiling and its eight-line comment. Deferred to §7.

**Also not changed:** `requires-python = ">=3.10"` stays. No 3.11+ syntax in the new package; `tomllib` only behind the `sys.version_info >= (3, 11)` / `tomli` fallback `tools/pb-appeon-index/src/pb_appeon_index/config.py:25-29` already models. (Phase 1 needs no TOML at all.)

**CI, `.github/workflows/ci.yml`:**
- `:65` → `mypy tools/pb-source-analyzer/src tools/pb-appeon-index/src tools/pb-ai-code/src`. Do **not** collapse to `mypy tools`: it fails with `Duplicate module named "tests"`.
- `:62` → leave `ruff format --check tools tests` exactly as written, and add a comment saying why it is path-scoped: `ruff format --check .` fails today on `skills/appeon-query/SKILL.md` and `skills/pb-review/SKILL.md` because ruff 0.16 formats Python inside Markdown fences.
- `:12-14` → rewrite the comment. It currently justifies `windows-latest` with "the link tests run `scripts/install-skills.ps1` for real", which the port makes false. The true reason: the install writes Windows paths and a `.claude/` layout, and the link check runs against what lands.

---

## 3. Package layout

```
tools/pb-ai-code/
├── src/pb_ai_code/
│   ├── __init__.py        package docstring, verb list, "python -m pb_ai_code"
│   ├── __main__.py         argparse surface, main(argv) -> int
│   ├── kit.py              locate + describe the bundled payload
│   ├── provenance.py       version, git identity, dirty flag
│   ├── harness.py          adapter dataclasses + registry
│   ├── plan.py             PlanRow, plan construction, source validation
│   ├── apply.py            copy semantics + the link rewrite
│   ├── mcpconfig.py        canonical block, merge, outcomes, duplicate scan, write
│   ├── appeon.py           index discovery + note
│   ├── marker.py           marker rendering, writing, parsing (for status)
│   ├── gitignore.py        the check-ignore hint
│   └── report.py           every stdout string, in one place
│   └── _kit/               (present only in a built wheel — force-included)
└── tests/                  unit tests
```

**No `__version__` literal.** Both existing `__init__.py` files carry a stale `__version__ = "0.0.1"`; that literal is what made pb-orca-mcp v0.2.0 introduce itself as 0.1.0. `provenance.py` derives everything from `importlib.metadata.version("pb-ai-code")`.

**`kit.py`: how bundle content is located at runtime.**

```python
def kit_root() -> Path:
    # 1. Packaged payload (wheel / uvx). Verified: nothing is inside a zip in a
    #    uv ephemeral environment, so the Traversable is a real directory.
    with resources.as_file(resources.files(__package__) / "_kit") as p:
        if (p / "skills").is_dir():
            return p
    # 2. Editable install / running from a checkout. force-include content does
    #    NOT exist in an editable install (verified), so this branch is the dev
    #    loop. Search upward for a SENTINEL — do not count parents; parents[4]
    #    is right only for the tools/<name>/src/<pkg>/ depth this happens to have.
    for parent in Path(__file__).resolve().parents:
        if (parent / "skills").is_dir() and (parent / "harness" / "mcp-servers.json").is_file():
            return parent
    raise KitNotFound(...)
```
Exposed: `skills_dir`, `commands_dir`, `docs_dir`, `harness_dir`, `mcp_servers_file`, `settings_file(harness_id)`, `iter_skills()` (sorted, case-insensitive), `iter_command_files()` (sorted, exact `.md` suffix), `is_checkout` (branch 2 was taken).

Rejected: `[tool.hatch.build.targets.shared-data]`. It reaches the uvx runtime (verified: `sys.prefix/share/pb-ai-code`) but is not addressable by `importlib.resources`, is not co-located with the code, and is unbound to the package on uninstall. Rejected: moving `skills/` under the package, `.gitignore:39-49`, `scripts/install-skills.ps1:14-21` and `tests/test_pins_in_sync.py:96` all address the canonical top-level layout.

**`provenance.py`** returns a frozen `SourceIdentity(version, origin, sha, branch, dirty)`:
1. `kit.is_checkout` and `git -C <root>` succeeds → `sha`, `branch`, `dirty` from `rev-parse --short HEAD`, `rev-parse --abbrev-ref HEAD`, `status --porcelain` (untracked counted).
2. else PEP 610: `importlib.metadata.distribution("pb-ai-code").read_text("direct_url.json")` → `vcs_info.requested_revision` and `commit_id`.
3. else version only.
Git absent or failing is never fatal here.

**`report.py`** owns every literal the installer prints. One module so the golden tests have a single owner and a string cannot drift in two places.

---

## 4. Command surface

### Stream discipline

`install` writes its **entire report to stdout**, in a fixed order, single stream. stderr carries only fatal error messages and unexpected tracebacks. This deviates from the two existing tools (progress → stderr, payload → stdout) deliberately: the report *is* the contract here, an agent parses it, and splitting it across two streams destroys the ordering when they are redirected separately. `status --json` restores the convention: JSON on stdout, nothing else.

No ANSI colour when stdout is not a TTY.

### `pb-ai-code install`

```
usage: pb-ai-code install [-h] [--target PATH] [--harness {claude-code,generic}]
                          [--skills-dir REL] [--commands-dir REL]
                          [--skip-mcp-config] [--dry-run]
```
Long options only (house rule: not one short flag exists in either CLI). Defaults in module-level `_DEFAULT_*` constants.

| flag | default | notes |
|---|---|---|
| `--target PATH` | `.` (cwd) | must exist and be a directory; never created |
| `--harness NAME` | `claude-code` | `type=str.lower`; `choices=("claude-code","generic")` |
| `--skills-dir REL` | none | required for `generic`, rejected for `claude-code`; target-relative only |
| `--commands-dir REL` | none | optional; must be a sibling of `--skills-dir` |
| `--skip-mcp-config` | off | |
| `--dry-run` | off | |

Top-level: `pb-ai-code --version` prints `importlib.metadata.version("pb-ai-code")`, exit 0.

### `install` stdout, line by line

`{S}` = kit root abbreviated to `<src>`, `{T}` = target abbreviated to `<dst>` (literal string replacement, as ps1:403-404). Paths use the platform separator.

```
(blank)
Source:  pb-ai-code 0.5.0 (git+https://github.com/restoresrl/pb-ai-code)
[WARN: source repo has uncommitted changes; the install may include unversioned work.]      # checkout+dirty only
Target:  C:\proj\my-pb-app
Harness: claude-code
(blank)
[Note: no commands directory for this harness; skipping 2 command file(s).]                 # generic w/o --commands-dir
[Every flow is also reachable as a skill of the same name.]
[(blank)]
skill     <src>\skills\appeon-query -> <dst>\.claude\skills\appeon-query
...                                                                                          # one per plan row, plan order
command   <src>\commands\pb-format.md -> <dst>\.claude\commands\pb-format.md
docs      <src>\docs\pb-antipatterns -> <dst>\.claude\pb-ai-code-docs\pb-antipatterns
docfile   <src>\docs\wiki-notes.md -> <dst>\.claude\pb-ai-code-docs\wiki-notes.md
settings  <src>\harness\claude-code\settings.json -> <dst>\.claude\settings.json
mcp       <src>\harness\mcp-servers.json -> <dst>\.mcp.json  (merged; other servers preserved)
marker    <dst>\.claude\_installed-from-pb-ai-code.txt
rewrite   ../../docs/ -> ../../pb-ai-code-docs/  in the installed skills
(blank)
```
Op field is left-aligned in **9 columns** followed by one space. `mcp` row alternatives: `mcp       skipped (--skip-mcp-config)` and `mcp       <src>\harness\mcp-servers.json -> printed below (location is client-specific)`.

Dry run stops here with:
```
Dry run. No changes written.
[Would configure pb-appeon-index -> <db>]      or   [Note: <appeon note>]
[MCP: would add pb-orca; would leave postgres] 
```
…and exits 0 having created nothing.

Otherwise:
```
Installed skill     appeon-query                                    # leaf only, one per plan row
...
Installed settings  settings.json
[WARN: replaced an existing .claude\settings.json whose content differed.]   # NEW, see ledger 22
Rewrote knowledge-base links in 5 skill file(s).
```
Then exactly one MCP branch:
```
# (a) skipped
Skipped MCP config (--skip-mcp-config). The skills expect the pb_* tools to be reachable.

# (b) merged  (preceded, if applicable, by the duplicate-server block below)
Installed mcp       .mcp.json  [pb-orca (added); pb-appeon-index (added); kept: postgres]

# (c) unparseable target
(blank)
WARN: C:\proj\my-pb-app\.mcp.json is not valid JSON - leaving it untouched.
      Merge this into its 'mcpServers' object by hand:
{ …the block, 2-space indent… }
(blank)

# (d) generic
(blank)
MCP config: add these servers to your client's MCP configuration.
Same JSON for every MCP client; only the file it goes in differs.
{ …the block… }
(blank)
```
Duplicate-server block (before (b), once per offending key, wrapped in blanks):
```
WARN: the target already has a server 'orca' that runs pb-orca-mcp, which is what
      this kit installs as 'pb-orca'. Two of them means two processes
      competing for a single-session ORCA library, duplicate tools under different
      prefixes, and only one of them matching the permission allowlist.
      Left in place - it is your file. Remove 'orca' unless you meant to keep it.
```
Appeon block (suppressed entirely by `--skip-mcp-config`):
```
Appeon index      C:\Users\me\.pb-appeon-index\index.db
                  referenced, not copied - rebuilding it once updates every project
```
or
```
(blank)
Note: pb-appeon-index NOT configured - missing the index database
      The PowerScript reference lookups degrade to reading the
      database directly, or to web fetches. To build the index:
        git clone https://github.com/restoresrl/pb-ai-code
        cd pb-ai-code ; uv venv ; uv pip install -e ".[dev]"
        .venv\Scripts\pb-appeon-index update --db %USERPROFILE%\.pb-appeon-index\index.db
      Then re-run this installer and the server is configured.
```
Tail:
```
(blank)
Done.
[Restart your assistant to pick up the MCP config, then confirm the pb_* tools are listed (/mcp).]
(blank)
Note: '.claude' is not ignored by git in this project.
      The bundle is generated - update it by re-running pb-ai-code install, not by
      editing it - so it does not want committing. Suggested .gitignore lines:
        .claude/
        .mcp.json
```
`Done.` is **not** the last line when the gitignore note fires. Keep it that way (ledger 68).

### `pb-ai-code status`

```
usage: pb-ai-code status [-h] [--target PATH] [--json]
```
Text form (stdout):
```
pb-ai-code 0.5.0 (running)
Target:    C:\proj\my-pb-app
Marker:    .claude\_installed-from-pb-ai-code.txt
Installed: 2026-08-12 17:02:56 +02:00
Version:   0.5.0
Source:    pb-ai-code @ 0.5.0 (git+https://github.com/restoresrl/pb-ai-code, c26d4b6)
Harness:   claude-code
MCP:       .mcp.json  [pb-orca (added); pb-appeon-index (added)]
Appeon:    pb-appeon-index configured -> C:\Users\me\.pb-appeon-index\index.db
Contents:  12 entries
Up to date: yes
```
`--json` (stdout, `json.dumps(obj, indent=2)`):
```json
{"installed": true, "target": "...", "marker_path": "...", "installed_at": "...",
 "version": "0.5.0", "source": "...", "sha": "c26d4b6", "branch": null,
 "dirty": false, "harness": "claude-code", "mcp": "...", "appeon": "...",
 "contents": ["..."], "running_version": "0.5.0", "up_to_date": true}
```
`status` searches for a marker at every known harness location under the target: `.claude/`, then any `*/_installed-from-pb-ai-code.txt` one and two levels down. It performs **no network access** and needs no git.

### Exit codes

| code | `install` | `status` |
|---|---|---|
| 0 | success: **including** every warning path: duplicate ORCA server, unparseable target `.mcp.json`, missing Appeon index, no commands directory, bundle not gitignored, dirty source | marker found and parsed |
| 2 | usage error: target missing or not a directory, absolute/escaping `--skills-dir`/`--commands-dir`, non-sibling `--commands-dir`, `--skills-dir` with `claude-code`, unknown harness, argparse errors | usage error |
| 3 | none | no marker at this target (documented deviation: agents branch on "installed?" without parsing) |
| 1 | unexpected: payload not found, copy failure, permission error. Anticipated failures print one line `pb-ai-code: <message>` on stderr with **no traceback**; unanticipated exceptions keep the traceback (house rule) | same |

The "warnings exit 0" rule is load-bearing: three existing assertions depend on it (`tests/test_installer_mcp_merge.py:56`).

---

## 5. The harness adapter abstraction

The PowerShell `switch ($Harness)` sets five scalars (ps1:289-306). That shape cannot express Codex (TOML, no project commands directory, a trust gate), OpenCode (different key, fused `command` array), Continue (YAML, one file per server) or a dual `.claude` + `.agents` install. Shape it as *a list of roots plus an MCP emitter* now, implement only what exists today.

```python
@dataclass(frozen=True)
class SkillRoot:
    skills_rel: str                       # ".claude/skills"
    commands_rel: str | None              # ".claude/commands"
    @property
    def docs_rel(self) -> str: ...        # parent(skills_rel)/"pb-ai-code-docs"  (ledger 20)
    @property
    def marker_rel(self) -> str: ...      # parent(skills_rel)/"_installed-from-pb-ai-code.txt"  (ledger 54)
    @property
    def bundle_root(self) -> str: ...     # first path segment — the gitignore hint's subject

@dataclass(frozen=True)
class McpTarget:
    rel_path: str | None                  # None => print the block
    dialect: str                          # "mcp_json" | "codex_toml" | "opencode_json" | "continue_yaml"
    scope: str                            # "project" | "user"
    write_mode: str                       # "merge" | "own_file" | "print_only"
    note: str | None                      # printed when the file is written but may be inert

@dataclass(frozen=True)
class ExtraFile:
    src_rel: str                          # "harness/claude-code/settings.json" (kit-relative)
    dst_rel: str                          # ".claude/settings.json"            (target-relative)
    mode: str                             # "overwrite"

@dataclass(frozen=True)
class Adapter:
    id: str
    roots: tuple[SkillRoot, ...]
    mcp: McpTarget | None
    extra_files: tuple[ExtraFile, ...]
    restart_hint: str | None
    gaps: tuple[str, ...]                 # printed as "Note: …" — what this harness cannot do
```

**Phase-1 registry: two entries.**

```python
CLAUDE_CODE = Adapter(
    id="claude-code",
    roots=(SkillRoot(".claude/skills", ".claude/commands"),),
    mcp=McpTarget(".mcp.json", "mcp_json", "project", "merge", note=None),
    extra_files=(ExtraFile("harness/claude-code/settings.json", ".claude/settings.json", "overwrite"),),
    restart_hint="Restart your assistant to pick up the MCP config, then confirm the pb_* tools are listed (/mcp).",
    gaps=(),
)
# "generic" is built at run time from --skills-dir / --commands-dir:
#   roots=(SkillRoot(skills_dir, commands_dir),)
#   mcp=McpTarget(None, "mcp_json", "project", "print_only", note=None)
#   extra_files=()   restart_hint=None
```
For `claude-code` every derived path is byte-identical to today (`parent(".claude/skills")` is `.claude`, so both `docs_rel` and `marker_rel` reproduce ps1:296 exactly).

**Rules that make later harnesses drop in without rework:**
- The plan builder iterates `adapter.roots`. With one root the plan is exactly today's.
- The link rewrite runs **per root**; the doc trees are copied **per root** (a shared tree via symlink is not safe on Windows without Developer Mode).
- One marker **per root**.
- The gitignore hint loops over `{root.bundle_root for root in roots}` ∪ `{written mcp paths}`: today `.claude` + `.mcp.json`, i.e. unchanged output.
- The MCP layer is two pure functions: `emit(servers: dict, dialect) -> bytes` and `merge(existing: bytes | None, servers: dict, dialect) -> MergeResult(text, outcomes, warnings, wrote)`. Only `mcp_json` is implemented; the other three raise `NotImplementedError` and are listed in §7.
- `harness/mcp-servers.json` stays the single source of truth for the server set, whatever the dialect: `tests/test_pins_in_sync.py:93-121` asserts that file decides the pin.

**Documented-but-not-implemented targets** (verified paths, for whoever adds them; keep this table in `harness/README.md`):

| harness | skills root(s) it reads | commands | MCP config | dialect / mode |
|---|---|---|---|---|
| codex | `.agents/skills` only | none project-scoped (prompts are user-scoped and deprecated) | `.codex/config.toml` | `codex_toml` / print_only until a comment-preserving writer exists: trust-gated, may be inert |
| cursor | `.cursor/skills`, `.agents/skills`, `.claude/skills` (compat) | `.cursor/commands/*.md` | `.cursor/mcp.json` | `mcp_json` / merge |
| opencode | `.claude/skills`, `.agents/skills`, `.opencode/skills` | `.opencode/commands/*.md` (verify plural on disk) | `opencode.json` | `opencode_json` / merge |
| continue | `.continue/skills`, `.claude/skills` | `.continue/prompts/*.prompt` | `.continue/mcpServers/pb-ai-code.yaml` | `continue_yaml` / own_file (safest target of all) |
| windsurf/devin | `.claude/skills`, `.agents/skills`, `.windsurf/skills`, `.devin/skills` | `.windsurf/workflows` (Cascade-only, being migrated away) | `~/.codeium/windsurf/mcp_config.json` | `mcp_json` / print_only (user scope) |
| aider | none | none | none |: (`gaps=("no skills, no MCP, no auto-loaded instructions",)`) |

`.claude/skills` + `.agents/skills` together cover every tool in scope that has skills at all.

**Never written by any adapter:** `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`, `.windsurf/rules/`, `.continue/rules/`. Those are the project's own committed prose; the kit's rule is that a consumer commits nothing agentic. Where a pointer is wanted, print a line for the user to paste.

**`harness/claude-code/settings.json` stays claude-code-only.** No other tool examined has a per-MCP-tool allowlist keyed on `mcp__server__tool`; do not generalise it into a "permissions" concept.

---

## 6. Test plan

**Where.** `tools/pb-ai-code/tests/`, unit tests for the merge, the plan builder, the marker renderer, path validation, the dialect emitter. Root `tests/`, the cross-cutting end-to-end ones that already exist and must keep their identity: `test_installer_mcp_merge.py`, `test_links_resolve.py`, `test_pins_in_sync.py`.

**How.** End-to-end tests invoke `[sys.executable, "-m", "pb_ai_code", "install", ...]` via `subprocess.run`, never `main()` in-process: the house rule from the mcp 2.0.0 incident is that a test which does not cross the boundary does not prove the boundary works, and a subprocess also exercises the entry point `uvx` will use. Nothing is mocked anywhere in this repository; keep it that way. Every new test module opens with a docstring naming what went wrong once.

**Delete the `shutil.which("pwsh") or shutil.which("powershell")` guards** (`test_installer_mcp_merge.py:33-37`, `test_links_resolve.py:112-114`). They were the mechanism by which the link check could silently no-op. Say so in the CHANGELOG.

### Tests by ledger item

| test | covers |
|---|---|
| `test_wheel_payload_matches_git` (root) | 2.6: build the wheel, diff `pb_ai_code/_kit/**` against `git ls-files skills commands harness docs/pb-antipatterns docs/pb-source-format docs/wiki-notes.md`; assert equal and assert no `*.db` in the wheel. **The only thing standing between a refactor and shipping an installer with nothing to install.** |
| `test_version_matches_tag` (extend `test_pins_in_sync.py`) | 2.2: when HEAD carries a tag, `importlib.metadata.version("pb-ai-code")` equals it with the leading `v` stripped |
| `test_links_resolve.py::test_installed_layout_has_no_dead_links` (rewritten) | 15, 18, 19, 20, 28, 30: parametrised over claude-code and generic; plus a new assertion that zero installed files contain `../../docs/` |
| `test_every_skill_installs_whole` | 15: planted `skills/pb-review/references/x.md` arrives |
| `test_commands_flat_md_only` | 17: pre-existing `my-command.md` survives; no subdirectory copied |
| `test_docs_placement` | 20: `--skills-dir a/b/skills` → `a/b/pb-ai-code-docs/`, marker at `a/b/` |
| `test_nothing_else_is_copied` | 21: no `install.md`, `*.db`, `appeon-index/`, `install-skills.ps1` under the target |
| `test_self_install_copies_docs` | 29: install into the checkout itself; docs present, links rewritten |
| `test_rewrite_count_and_bytes` | 28, 27: `Rewrote … 5 skill file(s).`; 13 occurrences in `pb-src-format`; every installed file byte-identical to source except the substitution; CRLF/LF/BOM counts preserved per file |
| `test_delete_before_copy` | 24: planted ghost file and hand edit both gone; no doubled path |
| `test_readonly_destination` | 25: read-only installed `SKILL.md` and read-only tree are replaced, exit 0 |
| `test_no_pruning` | 26: five planted survivors (stale skill, own skill, stale doc tree, loose docs file, own command) all survive; none in Contents |
| `test_settings_overwrite` | 22, 23: byte-identical to canonical, unrelated key gone, WARN line printed, `generic` writes none |
| `test_installer_mcp_merge.py` (ported) | 42, 43, 36: the two duplicate shapes verbatim, the no-false-positive case, malformed-left-alone; keep `returncode == 0`, keep asserting on stdout+stderr combined **and add a stream-specific assertion** |
| `test_merge_preserves_top_level_and_order` | 34: sibling top-level key keeps value *and* position; `postgres` stays first |
| `test_owned_key_case_insensitive` | 35: `PB-Orca` becomes one `pb-orca` in the original position |
| `test_empty_missing_null_config` | 37: three cases all merge |
| `test_strict_json` | 36, 38: trailing comma, `//`, `/* */`, `NaN` all refuse-and-print; BOM'd valid file merges and comes back BOM-free |
| `test_mcpservers_non_object` | 39: `{"mcpServers":"oops","other":1}` left byte-identical |
| `test_outcome_vocabulary` | 40, 41: added / already current / updated / `kept:`; reordered keys report `already current` |
| `test_write_mechanics` | 46: no BOM, one trailing newline, 2-space indent; new files use CRLF, existing LF stays LF; 12-level-deep foreign server survives |
| `test_duplicate_scan_extended` | 42, 44: case-insensitivity, bare-path shape, `pb_appeon_index` shape, the `$ourPackages` self-check, duplicate still under `kept:` |
| `test_skip_mcp_config` | 48, 33, 53: file byte-identical, four suppressions, missing payload file no longer aborts, `# Appeon: not evaluated` |
| `test_generic_prints_block` | 47: no `.mcp.json` anywhere, block on stdout, marker records the outcome |
| `test_marker_golden` (per harness) | 55-61: golden fixture with timestamp/version/sha normalised; byte assertions: no BOM, CRLF only, one trailing CRLF, ASCII |
| `test_marker_contents_order` | 59: equals the plan destinations in plan order; `.mcp.json` and the marker itself absent |
| `test_dirty_warning` | 3, 4, 5: one untracked file flips both warnings; clean source has neither |
| `test_stdout_golden` (4 modes) | 64-68: claude-code, generic, `--skip-mcp-config`, `--dry-run`; absolute paths/sha/timestamp normalised; assert stderr empty on success |
| `test_gitignore_hint_crlf_blank_line` | 70: CRLF `.gitignore` with a blank line and no rule → the note **must** print. The regression that made the hint never fire. |
| `test_gitignore_hint_gating` | 69, 71, 72, 73: ignored repo → silent; non-git target → silent, exit 0; nested-repo target → the note says which repo |
| `test_exit_codes` (table) | 74, 8, 10, 11, 30: every invocation with its code; stdout empty on failure paths; no traceback on code 2 |
| `test_dry_run_writes_nothing` | 75: `os.listdir(target) == []`, exit 0, plan printed |
| `test_status` | 77: round-trip install → status; text and `--json`; exit 3 with no marker; exit 2 on a bad target |

### Not testable automatically, and why

1. **That an assistant actually loads the installed skills.** No client is on CI. Mitigated by the link tests and by the marker; verified by hand per release against Claude Code.
2. **The Appeon "configured" branch on CI.** `index.db` is gitignored, present on a developer machine, absent on CI. Keep the existing property assertion (`set(merged) - {...} <= {"pb-appeon-index"}`, `test_installer_mcp_merge.py:130`) rather than a snapshot. The failure branch *is* testable (point `PB_APPEON_INDEX_DB` at a non-existent path).
3. **`uvx --from git+https://…@tag` end to end.** Needs network, `git` on PATH, and a pushed tag that does not exist until the release commit. Add instead a CI job that does `uv build` then `uvx --from <local wheel> pb-ai-code install` into a temp dir: that exercises the packaged-payload branch of `kit_root()` without the network. The real git-URL run stays a manual release-gate step.
4. **The MAX_PATH / deep `UV_CACHE_DIR` clone failure** (`fatal: failed to unlink … Filename too long`, reported by uv only as `Git operation failed`). Environment-dependent; document it in `docs/install.md`.
5. **"Restart your assistant"** and Claude Code's untrusted-folder pending-approval state.
6. **Every other harness.** Nothing is implemented, nothing is installed on CI.
7. **Windows PowerShell 5.1 / non-Windows hosts.** CI is `windows-latest` only. Not claimed this phase.

---

## 7. What this phase deliberately does NOT do

- **No `check-update`, `update`, `uninstall`, `report`.** `status` reads the marker offline; nothing contacts GitHub. The marker gains `# Version:` so those verbs become possible, not so they exist.
- **No file inventory or hashes in the marker.** `# Contents:` keeps listing directories, so an updater cannot distinguish a kit file from a user edit. That is the prerequisite for `update`/`uninstall`, and it is deferred with them.
- **No pruning.** A skill or doc tree removed upstream stays in the target forever (ledger 26). Pruning by a previous marker's Contents list is the eventual design; it needs a decision about a user's own skill sitting in the same directory.
- **No Appeon index as a release asset**, no `~/.pb-ai-code/` cache, no `pb-ai-code fetch-index`. Phase 1 only re-roots the *discovery* (env var → `~/.pb-appeon-index/index.db` → checkout) and rewrites the server entry to use `uvx` instead of a checkout `.venv`. Building the index remains a developer task from a clone.
- **No dependency extras split.** Cold start stays 38 packages / ~11.5 s. Splitting forces `--from "pb-ai-code[tools] @ git+…@tag"` in `harness/mcp-servers.json`, `docs/install.md`, `docs/appeon-index/README.md` **and** in the `pb-appeon-index` server entry this CLI writes: coordinated churn for an optimisation.
- **No `settings.json` merge.** Full overwrite is preserved (ledger 22); only a warning line is added. The merge is the right answer and it is a separate decision.
- **No harness adapters beyond claude-code and generic**, and no MCP dialect beyond `mcp_json`. The abstraction exists (§5); the entries do not.
- **No `pb-format` promotion**, no change to any skill's content beyond the two coordinated edits required by ledger 57 (`skills/pb-review/SKILL.md`, `docs/wiki-notes.md`).
- **No removal of `scripts/install-skills.ps1`.** It stays in-tree for one release with a deprecation banner in its `.DESCRIPTION` and a pointer at the CLI, and it stops being what CI's link test drives. Delete it in the release after. Its two stale comments (ps1:115-117, 26-31) should be corrected in the same commit as the port, so nobody reads the port against a source whose prose lies.
- **No claim of Linux/macOS support.** The code becomes path-portable; nothing is verified off Windows.
- **No `install --json`.** Only `status` is machine-readable this phase.

---

## 8. Contradictions and open questions

### Contradictions between agents or between code and prose

**C1: `settings.json` risk rating.** Area 1 rated `settings-json-full-overwrite` *medium*; Area 4 rated the same behaviour *high* and called it "the single most destructive behaviour in my area". Both describe identical, verified behaviour (verbatim clobber, no merge, no backup). **Resolution: high.** Nothing in CHANGELOG, `docs/install.md` or the file's own `_comment` addresses collision with a consumer's own hooks.

**C2: do the comments or the code describe the self-install?** `scripts/install-skills.ps1:115-117` and `:26-31` say the doc trees are not copied on a self-install. The code copies them unconditionally (`:376-389`, `:451-461`), the checkout's own `.claude/pb-ai-code-docs/` exists, and commit e04a11d explicitly recants the comment ("The rewrite applies to a self-install too, which contradicts what I claimed while designing this"), as does `docs/install.md`. **Resolution: the code is right; the comments are stale.** A port that implements the comments fails ledger 29.

**C3, where does the Appeon "configured" sentence appear?** `docs/install.md:318-321` advertises stdout printing `Appeon index: pb-appeon-index configured -> <db>`. The script prints `Appeon index      <db>` plus a second line (`:540-541`); the `configured ->` sentence is the **marker's** value (`:497`). **Resolution: the script is the contract; the doc is wrong.** Fix `docs/install.md` in the port commit.

**C4, marker location under `generic`.** Code puts it inside the skills directory (`:304`); `skills/pb-review/SKILL.md:771-773` and `docs/wiki-notes.md:77` both say the bundle directory. **Resolution: change the code** (ledger 54), the docs already describe the better rule, claude-code is unaffected, and a review that cannot find the marker is instructed to report that fact, so silent drift here is expensive.

**C5, "the MCP block is identical for every client".** Stated in `harness/README.md:10` and `:14` and `docs/install.md:149`; the script even prints it (ps1:527). The harness research contradicts it with primary sources: Codex CLI is TOML `[mcp_servers.<name>]`; OpenCode uses key `mcp` with `command` as a single fused array and `environment` instead of `env`; Continue is YAML with a `name` field inside the entry; Aider has no MCP at all. Only Cursor and Windsurf share the shape. **Resolution: the research is right.** Fix the three prose locations in the port commit. That sentence is exactly what would make a porter build a one-shape emitter. Leave the printed string for now (it is only shown on the `generic` path and only Claude Code's contract is verified anyway), or reword it to "Same JSON for Claude Code and Cursor; other clients use a different shape".

**C6, version identity mechanism.** The conventions agent recommends setting `version` to the tag by hand plus a test; the packaging agent verified `hatch-vcs` end-to-end through uvx (tag → `0.5.0`, one commit past → `0.5.1.dev1+g<sha>`). **Resolution: hatch-vcs**, because the failure it prevents already happened here (`pyproject.toml:7` is three minors stale) and because the dev-build suffix makes a non-release honest in the marker. Two costs to accept: `fetch-depth: 0` is mandatory (a shallow clone silently yields `0.1.dev1+g<sha>` with only a `UserWarning`), and in an editable install the version is frozen at install time until reinstall. If those are unacceptable, the fallback is a static version plus `test_version_matches_tag`, the test is required either way.

**C7: stream discipline.** House convention (both existing CLIs) is progress → stderr, payload → stdout. The PowerShell installer puts everything on stdout, and the parent task's premise is that an agent parses stdout. **Resolution: `install` uses stdout for the whole report** (§4), documented as a deviation with its reason; `status --json` restores the convention.

**C8: `already current` semantics.** PowerShell compares compressed-JSON strings, so a key-reordered but identical server reports `(updated)`; a Python dict comparison reports `already current`. Nothing tests it. **Resolution: dict equality** (ledger 41), with a test, because the file is rewritten either way and the word should be true.

**C9, case-sensitivity of server keys.** PowerShell's case-insensitivity is accidental (a collection default) but it is what stops `PB-Orca` becoming a second ORCA server, the exact fault the duplicate warning exists for. **Resolution: implement it explicitly and canonicalise the key to `pb-orca`**, because `harness/claude-code/settings.json` hard-codes `mcp__pb-orca__*` and a differently-cased key silently voids every permission allowance. One agent observed the merged result as "a single `pb-orca` entry"; whether PowerShell kept the original spelling was not established: **verify before writing the test's expected spelling** (see V5).

**C10, `-SkillsDir` absolute.** Help (ps1:69-71) promises it; `Join-Path` concatenates (`C:\tgt\D:\abs\skills`). Python's `Path` join would silently *implement* the documented behaviour and install outside the target. **Resolution: refuse** (ledger 11), neither the docs nor the code describe an intended behaviour, and refusing is the only option that cannot surprise.

### Load-bearing items marked assumed/unverified: verify before relying

**V1, does `uvx --from git+https://github.com/…` need `git` on PATH?** Verified only against a `file://` URL, where removing git produced `Git operation failed`. uv logs "Attempting GitHub fast path" for github.com URLs, which may not need git. **Assume git is required and document it** until tested against github.com, the failure message is unreadable.

**V2: does uv write PEP 610 `direct_url.json` for VCS installs?** The provenance chain's branch (b) depends on it (ledger 2, 57). pip does. If uv does not, `# Source:` falls back to version-only for uvx installs and the `To update:` recipe must synthesise `@v<version>` instead of echoing the requested revision.

**V3, `pb-appeon-index update` under uvx is very likely broken.** `tools/pb-appeon-index/src/pb_appeon_index/__main__.py:25` computes `_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent.parent / "config.toml"`, which in a wheel resolves to `<site-packages>/../config.toml`, and `config.toml` is not in the wheel at all (only the `src` package is). `_DEFAULT_DB` is `docs/appeon-index/index.db` **relative to cwd**. So the "build the index" recipe must **not** be `uvx … pb-appeon-index update`; §4 prints a clone-based recipe with an explicit `--db`. Confirm, and if the uvx path is wanted, force-include `tools/pb-appeon-index/config.toml` and give `_DEFAULT_CONFIG` an `importlib.resources` fallback.

**V4, does anything parse the marker by regex?** Three readers are documented (`skills/pb-review/SKILL.md:721, 771-773, 812-818`; `docs/wiki-notes.md:76-80`; `skills/appeon-query/SKILL.md:85`) and all appear to be instructions to an LLM reading by eye, not code. Confirm before changing `# Source:` (ledger 57), and change those two documents in the same commit regardless.

**V5: PowerShell's key spelling on a case-insensitive replace.** See C9.

**V6: the exit-128 leak.** One agent observed `pwsh -File install-skills.ps1` exiting 128 when the target is not a git repo, because the final `git rev-parse --is-inside-work-tree` leaks `$LASTEXITCODE`; CI is green, so `pwsh -File` presumably masks it. Irrelevant to the port's own code, but it matters while both installers coexist and any test asserts a zero exit.

**V7: `--strict-markers` is on** (`pyproject.toml:95`); register any new pytest marker or collection fails.

**V8: ruff's Markdown formatting** was verified on 0.16.1; `pyproject.toml:47` allows `ruff>=0.6`. If CI ever resolves an older ruff, `ruff format --check .` would pass and the path scoping would look arbitrary again. Consider raising the floor to `ruff>=0.16` so the reason stays legible.

**V9: platform coverage.** Everything in the packaging research was run on Windows with uv 0.11.18. Nothing was run on Linux, macOS, or uv < 0.11. `uv tool install` (persistent) and its upgrade semantics were not exercised.

**V10, the two planning documents are untracked and written in Italian.** `AGENTS.md:153` makes English non-optional for docs, so `docs/plan-self-bootstrap.md` and this file must be translated before either is committed, or left untracked. Both originally quoted the install command with a version pin; the pin test caught it on the first run (see V11; that is not hypothetical) and both were rewritten to name the repository without a tag. Do not put the tag back into a URL in prose: untracked-but-not-ignored files are in scope for that test, so an uncommitted note constrains the tag you cut.

**V11, the CHANGELOG pin trap.** `HISTORY_FILES = {"CHANGELOG.md"}` exempts the changelog from the bare-`@version` rule but **not** from `_pins()`. A v0.5.0 entry quoting the full `uvx --from git+https://github.com/restoresrl/pb-ai-code …` command passes the day it is written and breaks `test_each_sibling_repo_is_pinned_to_one_ref` the day the pin moves to v0.5.1. Write the command without the tag, or name the version in prose. Do **not** add `--python 3.12-x86` to the self-pin. That flag exists for `pborc.dll`, and the x86 test only fires on lines containing `pb-orca-mcp@` (`tests/test_pins_in_sync.py:141-142`).

### Open questions the maintainer must answer before v0.5.0 is cut

1. Should an unparseable target `.mcp.json` still exit 0? Today the install "succeeds" while the block was only printed, and an agent driving `pb-ai-code install` cannot tell that from a full success without parsing stdout. Same question for `--skip-mcp-config` and the `generic` printed-block path. The spec keeps exit 0 (three existing assertions depend on it) and offers `status` as the machine-readable answer, but a distinct "installed with reservations" code is a live option.
2. Is `~/.pb-appeon-index/index.db` the standard location? It is what `mcp_server.py:36-45` already falls back to, which is why the spec picks it, but `docs/appeon-index/README.md` documents `docs/appeon-index/index.db` inside the workspace, and existing developers have their DB there. The port's discovery order handles both; the docs must pick one to recommend.
3. Does the commands directory survive at all? Claude Code has merged commands into skills and the skill wins on a name collision, Codex has no project-scoped commands directory, and the kit's own fallback line already says "Every flow is also reachable as a skill of the same name." Phase 1 keeps installing both for parity; deleting `commands/` is a separate, cheap decision.
4. What does `# Harness:` mean once an install can target several roots? The spec normalises to one adapter id per run; a future multi-root install needs either a list or one marker per root (the spec already writes one marker per root).