# `MessageBox` / `HALT` in a library a headless target also loads

## Smell

```pb
// in a userobject that lives in a framework library,
// linked by GUI executables and by Windows services alike
if bConnect then
    connect using trDup;
    if trDup.SQLCode <> 0 then
        MessageBox ( "Server connection fail", trDup.SQLErrText, StopSign! )
        HALT CLOSE
    end if
end if
```

## Why it bites

A `.pbl` does not know which executable will link it. In a workspace
where one framework library is shared between interactive applications
and services or API servers — the normal shape of a PowerBuilder
product line — every process-level decision taken inside that library
is taken on behalf of hosts the author never considered.

Two calls do the damage, and they fail differently:

- **`MessageBox` in a process with no interactive desktop** does not
  error and does not return. It posts a modal dialog to a window
  station nobody is watching, and the thread blocks there forever. From
  the outside the service is running, its process is alive, and it has
  simply stopped answering. There is no log line, because the code that
  would have logged is on the other side of the call.
- **`HALT` / `HALT CLOSE`** terminates the process. In a service that
  is a silent stop, usually followed by a restart by the service
  manager, then the same stop — a crash loop whose cause is three
  libraries away from the symptom.

Both are reasonable in the application layer, where something knows a
user is present. Neither is reasonable in a library, and the reason is
not style: the library cannot answer the question the calls presuppose.

`HALT` also skips cleanup. Anything the failing function had already
`CREATE`d is leaked, and any `finally` further up the stack does not
run — so the failure path is precisely where the state is worst.

## Idiomatic fix

Return the failure and let the caller decide. Most of these functions
already return a `boolean` that carries no information because it is
unconditionally `TRUE`:

```pb
if bConnect then
    connect using trDup;
    if trDup.SQLCode <> 0 then
        DESTROY trDup
        Return FALSE
    end if
end if

Return TRUE
```

Where the library needs to *report* rather than merely fail, throw —
the exception carries the message to whatever layer knows how to show
it, and it unwinds cleanly:

```pb
n_ex_connection ex

ex = create n_ex_connection
ex.SetMessage ( "connection failed: " + trDup.SQLErrText )
throw ex
```

If a genuine "shut the application down" semantic is needed from deep
inside the object graph, post an event up to the application object and
let the top level call `halt close`.

## How to find it

The question — *"is this library loaded by a target with no
interactive desktop?"* — is answerable mechanically, which makes this
one of the few antipatterns with a reliable detection recipe rather
than a judgement call:

1. Grep the library's sources for `MessageBox`, `HALT`, `MessageBox(`
   in NVOs and non-visual code.
2. **Get the target list from the `.pbw`**, via `pb_target_info` — not
   from a glob over `*.pbt`. The two disagree in both directions: a
   glob misses targets kept in subdirectories and picks up orphaned
   `.pbt` files no workspace declares any more. In the case below the
   glob said 14 and the workspace said 14, but they were not the same
   14, and the count came out wrong.
3. For each declared target, read the `.pbt`: it is text, and the
   `LibList` names the libraries verbatim. Any target that links this
   library and produces a service or a server is a match;
   `pb_target_info` on the survivors resolves the relative paths.

A hit inside a `window` or `menu` is usually fine — those cannot run
headless. A hit inside a `userobject`, a global function or an
application-level helper is the one to look at.

## Where it has been seen

- A warehouse-management product line (review run 2026-08-12): the
  transaction framework's `duplicate()` method used `MessageBox` +
  `HALT CLOSE` on connection failure. The library was loaded by **11 of
  the 14 targets** the workspace declares, **5 of them headless** — two
  REST servers and three Windows services — with an unattended ETL
  executable and a test runner as further candidates. It had no callers
  at the time, which is the only reason it had never fired; the finding
  was ranked on severity, not likelihood.

  The count took three attempts to get right, which is why step 2 above
  is worded the way it is: first from a summary rather than the files,
  then from a glob that silently disagreed with the workspace. Each
  wrong figure was plausible and none of them failed loudly.

  Worth noting how the count was obtained, because it is the step that
  turns this from an opinion into a finding: grep the `.pbt` files for
  the library name, then read the target table in the project's own
  `AGENTS.md` to see which of those targets have no desktop. Neither
  half is enough alone — the `.pbt` says who links it, the target table
  says who runs headless.

## Related

- [`exitprocess-in-destruction`](exitprocess-in-destruction.md) — the
  narrower, more violent case: process termination reached from a
  destructor. Same family — process-level control flow taken by library
  code — with the added trap that destructors run at times nobody
  chose.
