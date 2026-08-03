# `exitprocess(...)` called from a destruction chain

## Smell

```pb
event destructor;
    // attempting to "shut down" the object cleanly
    exitprocess(0)
end event
```

## Why it bites

`exitprocess()` is the runtime call that **terminates the
PowerBuilder process** — analogous to `ExitProcess()` from the
Win32 API. It is not a "destroy this object" call; it does not
release the receiver or run any further user-mode cleanup. It is
intended for fatal abort scenarios (e.g. unrecoverable license
check failure) where the application must be torn down
immediately.

When `exitprocess()` is placed inside a destructor or a regular
shutdown method, the consequence is:

1. The first time that object is destroyed (often very early in
   the app lifecycle, or during a deep-nested cleanup), the whole
   PB process dies.
2. The user sees the application disappear with no diagnostics,
   no error dialog, no save-prompt.
3. The actual cause is invisible from the symptom: the entire
   process is gone, including the call stack that would have told
   you what destructor it was.

The name confusion is genuine — `exitprocess` reads like
"finish this process / unit / scope" to anyone who has not
encountered the API before. Compounded by other "exit"-style
verbs in PB (`return`, `halt`, `halt close`), it is easy to grab
the wrong one without realizing.

## Idiomatic fix

```pb
event destructor;
    // ... real cleanup of internal state ...
    // nothing else — PB destroys the receiver after destructor returns
end event
```

For cleanup of internal state, just write the cleanup. PB
automatically frees the receiver after the destructor returns. If
you genuinely need to release subsidiary objects, do it
explicitly:

```pb
event destructor;
    if isvalid(this.inv_target) then
        destroy this.inv_target
    end if
end event
```

If you need a "graceful close the application" semantic from
deep inside the object graph, post an event up to the main
window or application object — let the top-level decide whether
to call `halt close` or equivalent. **Do not** call `exitprocess`
from a destructor.

## Where it has been seen

- The logging chain of a private PB framework (review run
  2026-05-20): a shutdown helper invoked `exitprocess(0)` thinking
  it was closing the logger; the host process died on the first
  sample log failure, leaving no diagnostics for the operator.

## Related

- [destroy on auto-instance shadowing](destroy-on-auto-instance.md)
  — sibling failure mode where a destruction call hits the wrong
  target.
