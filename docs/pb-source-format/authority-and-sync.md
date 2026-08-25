---
name: authority-and-sync
status: populated
description: The PBL is the operational authority for pb-ai-code. ws_objects is a PowerBuilder-managed version-control projection. Reads and searches may use the projection, but every create, modify, rename, and delete operation goes through ORCA and PowerBuilder performs the sync.
---

# PBL authority and `ws_objects` synchronization

PowerBuilder added `ws_objects/` so source-control systems could track
object source that otherwise lives inside binary `.pbl` libraries. The IDE
creates the projection when source control is enabled for the workspace.
From then on, PowerBuilder owns its contents.

For every `pb-ai-code` workflow, the `.pbl` is the operational authority.
The projection is a readable and diffable view of it, not a second copy for
an agent to maintain.

## The invariant

- Reading, searching, and diffing existing `.sr*` files is allowed.
- Creating, modifying, renaming, copying, or deleting files directly under
  `ws_objects/` is not allowed.
- Every object operation goes through an ORCA primitive that acts on the
  `.pbl`.
- PowerBuilder writes or removes the matching projection file.
- The caller checks `sync`, `sync_error`, and `synced_files` before calling
  the operation complete.

This applies even when the proposed edit already exists as text in a plan,
a patch, or a Git checkout. Text becomes a PowerBuilder change only after
ORCA imports it into the library and PowerBuilder reports a successful sync.

## Create, modify, and delete

| Operation | Primary action | Required projection result |
| --- | --- | --- |
| Create | Compile or import the new entry into the `.pbl` | `sync: "ok"`; the new `.sr*` appears in `synced_files` |
| Modify | Export to scratch, edit there, import into the `.pbl` | `sync: "ok"`; the existing `.sr*` appears in `synced_files` |
| Delete | Delete the entry through the ORCA library primitive | `sync: "ok"`; PowerBuilder removes the projected `.sr*` |

If the server does not expose deletion together with projection sync, the
missing behavior belongs in `pb-orca-mcp`. Removing the `.sr*` by hand is
not a fallback.

A failed sync is not a warning to postpone. The `.pbl` and projection now
disagree, so the workflow stops and reports `sync_error`.

## Scratch files are not a projection

Exports used for editing or comparison always name a `dest_dir` outside the
project. An agent may edit those scratch files because PowerBuilder does not
manage them. Importing one changes the `.pbl`; a successful import then asks
PowerBuilder to update the real projection.

Never copy the scratch file into `ws_objects/`. Never use a bulk export to
create `ws_objects/` for a `pbl_only` workspace. The developer enables Git
or SVN in the PowerBuilder IDE, and the IDE creates the projection.

## Reading the projection

A read-only flow may grep `ws_objects/` because it is much cheaper than
exporting every object. It must call the result a projection or search
surface, not the source of truth.

A clean Git or SVN status does not prove that the projection matches the
library. When identity matters, export the entry from the `.pbl` to scratch
and compare the complete files as bytes. Do not export into the projection
to perform the check; that would overwrite one side before comparing it.

## Handling a mismatch

A mismatch never establishes which side is correct.

- If the complete files are identical, continue.
- If they differ only in line endings, stop and report both byte counts.
  Refresh the projection from the `.pbl` through PowerBuilder by default.
- If the user explicitly chooses to normalize source held in the `.pbl`,
  export to scratch, normalize that scratch file, import it through ORCA,
  and verify the resulting sync. Keep this maintenance change separate from
  functional edits.
- If content differs, stop. The workspace may have an IDE refresh pending, a
  source-control update not yet consumed by PowerBuilder, or an earlier sync
  failure. Do not choose a winner.

In particular, do not import the checked-out projection into the `.pbl` just
because its CRLF form looks canonical. That reverses the authority without
establishing that its content is current.

## Git attributes

Git attributes control what Git stores; they do not make an object change
and must not rewrite the working files:

```gitattributes
*.sr* -text
*.pbl binary
*.pbd binary
```

Use `-text` for `.sr*` so Git preserves their bytes without disabling text
diffs. Use `binary` for `.pbl` and `.pbd`, which are opaque containers.

Changing `.gitattributes` and running `git add --renormalize` may replace
normalized blobs in the index. The bytes under `ws_objects/` must remain
unchanged. Hash them before and after the operation. The installer reports
bad attributes but never edits this project-owned file.

UTF-16 exports and OLE-bearing files can still look binary to Git even with
`-text`. Their bytes are protected, but their PowerScript should be reviewed
through the ORCA body while full-file comparisons remain binary.

## SVN

`ws_objects/` also supports SVN. Git's `-text` rule has no SVN equivalent in
this kit, and `no_git` does not mean that a workspace has no source control.
Do not add Git configuration to an SVN checkout. Inspect the effective SVN
properties and preserve the files byte for byte until an `svn:eol-style`
workflow has been verified against a real PowerBuilder workspace.

## Cross-references

- [encoding](encoding.md): BOM, workspace encoding, and line-ending rules.
- [style conventions](style-conventions.md): optional body normalization.
- [`pb-apply-plan`](../../skills/pb-apply-plan/SKILL.md): the write loop.
- [`pb-orca-mcp`](https://github.com/restoresrl/pb-orca-mcp): the primitives
  that change libraries and report projection synchronization.
