# Unchecked return of `FileOpen()` followed by silent `FileWrite()`

## Smell

```pb
long ll_fh

ll_fh = FileOpen("c:\logs\app.log", LineMode!, Write!, LockWrite!, Append!)
FileWrite(ll_fh, "starting up...")
FileWrite(ll_fh, "...module init ok")
FileClose(ll_fh)
```

## Why it bites

`FileOpen()` returns the file handle on success, or `-1` on
failure. The most common failure modes — file locked by another
process, directory permission denied, path that resolves to a
non-existent drive — are routine production hazards, not corner
cases.

When `FileOpen` returns `-1` and the code doesn't check:

- `FileWrite(-1, ...)` returns `-1` and **does nothing**. No
  exception. No console output. No fallback.
- The application proceeds as if logging succeeded.
- On the next failure that the operator would normally debug from
  the log, the log is empty or missing entirely, and the visible
  error has nothing to do with the actual root cause.

This is especially poisonous for logging code, because logging
is the thing operators reach for **first** when diagnosing a
problem. A silent log breaks the diagnostic chain at the worst
possible moment.

## Idiomatic fix

Check the handle, branch on failure, and either degrade
gracefully or fail loudly. For logging code specifically, prefer
loud failure during startup (so a misconfiguration is caught) and
graceful degradation later (so a transient disk issue doesn't
crash a long-running session):

```pb
long ll_fh
long ll_rc

ll_fh = FileOpen("c:\logs\app.log", LineMode!, Write!, LockWrite!, Append!)
if ll_fh = -1 then
    // route to secondary sink, or surface to user at startup
    return -1
end if

ll_rc = FileWrite(ll_fh, "starting up...")
if ll_rc = -1 then
    // write failed — disk full, handle invalidated, etc.
    FileClose(ll_fh)
    return -1
end if

FileClose(ll_fh)
return 0
```

For logger NVOs that wrap `FileOpen/FileWrite`, the constructor
or `open()` method should set an internal "ready" flag based on
the handle, and every `write()` should check the flag and
short-circuit if not ready. The first failed-to-open should be
visible somewhere (a fallback sink, a startup warning) so the
operator knows the primary log is disabled.

## Where it has been seen

- **Appeon's own SDI application template** — the code the PowerBuilder
  "Quick Application" wizard generates, so every application scaffolded
  from it carries this. The same hazard on a different API: the `clicked`
  event of the generated `m_print` menu item does

  ```pb
  ll_job = PrintOpen ( )
  lw_main.Print ( ll_job, 1, 1 )
  PrintClose ( ll_job )
  ```

  `PrintOpen()` returns `-1` when it cannot start a job — no printer, no
  default printer, spooler unavailable — and both following calls then run
  against an invalid handle and do nothing. The user clicks Print and
  nothing happens, with no error anywhere.

  The template gets it right one item over: `m_print_query.clicked` guards
  with `if ll_job <> -1`. Two adjacent menu items, inconsistent handling of
  the same sentinel. Observed on the PB 2022 R3 wizard output, review run
  2026-07-29.

- The logging chain of a private PB framework (review run 2026-05-20): the
  file-based log target opened the log file without checking the handle,
  then wrote to it. When the log directory was locked or missing, the
  logger was silently dead for the lifetime of the process.

## Related

- [isnull on numeric types](isnull-on-numeric.md) — the wrong way
  to check the failure return; `IsNull(ll_fh)` will not work.
- [space() with uninitialized buffer length](space-before-init.md)
  — similar "API return not checked" hazard with a different IO
  primitive.
