# `DisableBind=1` turns bind variables into inlined literals

## Smell

Two files, and neither looks wrong on its own.

In the transaction object's setup, usually far from any SQL:

```pb
event constructor;
params.append("DisableBind=1")
params.append("Identity='SCOPE_IDENTITY()'")   // needs DisableBind=1
params.append("StaticBind=1")
end event
```

In a completely different class, embedded SQL written the safe way:

```pb
select id into :ll_id
    from attr_table
    where owner_id = :ll_owner_id and
          name      = :ls_attr_name
    using itr_main;
```

## Why it bites

`:name` is the shape every reviewer is taught to trust. It is the
answer to "how do I avoid building SQL by concatenation", and finding it
is normally where the check ends.

`DisableBind=1` changes what it means. It tells PowerBuilder **not** to
bind input parameters to a prepared statement, and to substitute the
values into the statement text before sending it. The syntax at the call
site does not change; the mechanism underneath it does. So the property
the syntax is trusted for — *this value never becomes part of the SQL
text* — is no longer being provided, and nothing at the call site says
so.

What makes it a durable trap rather than a one-off:

- **The setting is nowhere near the SQL.** It lives in the transaction
  object's `DBParm`, set in a constructor two or three classes up an
  inheritance chain. A reviewer reading the statement has no local reason
  to go looking.
- **It is set for good reasons.** `DisableBind=1` is required for
  `Identity='SCOPE_IDENTITY()'` to work, and interacts with `NCharBind`
  and the date-format parameters. So the answer is never "turn it off";
  it is "know that it is on".
- **It is a property of the connection, not of the object.** Every
  statement on that transaction is affected — including the ones in
  classes written by people who never saw the constructor.

**What this page does not claim.** Whether inlining is *exploitable*
depends on whether PowerBuilder escapes quotes as it substitutes, and
that was not verified when this was found. It may well escape correctly,
in which case nothing is unsafe and the entry is still worth having,
because the review lesson does not depend on the answer: **when auditing
embedded SQL, read the transaction's `DBParm` before you conclude
anything from the statement in front of you.** A conclusion drawn
without it is a guess about a mechanism you did not check.

## Idiomatic fix

There is no code change to prescribe. There are two things to do.

**Settle it once, in the codebase that sets the flag.** The experiment
is small and most PB codebases already have the instrumentation: pass a
value containing a single quote, then read what actually reached the
server — a datastore's `sqlpreview` event captures the statement, and
`DBParm`-level tracing writes it to a log.

```pb
// in the datastore or transaction that carries the statement
event sqlpreview;
is_last_sql = sqlsyntax       // inspect this, not the source
end event
```

If the literal arrives doubled (`'O''Brien'`), PowerBuilder escapes on
inlining and the matter is closed — **record that in a comment next to
the `DisableBind` line**, which is the fix, because the next reader will
otherwise re-derive it or skip it.

**If it does not escape**, validate at the boundary where the value
enters the statement — an identifier against the identifier charset, a
free-text value through the codebase's own escaping helper — rather than
trying to remove `DisableBind`, which other behaviour depends on.

## How to find it

Before auditing any embedded SQL in a workspace, check the transaction
hierarchy once:

```
grep -rn 'DisableBind' --include='*.sr*' .
```

If it is set to `1` anywhere in the chain the statements run on, every
`:var` in that chain is a substitution, not a bind. Note it at the top
of the review so the rest of the reading happens with the right
assumption, and so the next reviewer does not have to find it again.

## Where it has been seen

- A warehouse-management framework (review run 2026-08-12). The
  transaction object's constructor set `DisableBind=1` with an adjacent
  comment block discussing `Identity=`, `NCharBind` and date formats at
  length — and nowhere noting that the setting changes what a bind
  variable is. Five functions on the persistence base class, two classes
  away, read and wrote a side table of user-supplied attribute names
  through embedded SQL with `:name` parameters throughout.

  Neither object is wrong on its own, which is the point: the finding
  only exists because two reviews of the same codebase met.

## Related

- [`isnull-on-numeric`](isnull-on-numeric.md) and
  [`pos-guarded-as-negative`](pos-guarded-as-negative.md) — the same
  shape of mistake at a smaller scale: a construct that reads as a
  guarantee while the mechanism underneath does not provide it.
