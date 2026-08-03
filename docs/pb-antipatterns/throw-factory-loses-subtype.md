# `catch (n_X ex) ... throw <factory>(...)` loses exception subtype

## Smell

```pb
try
    iuo_db.exec_sql(ls_sql)
catch (n_ex_db ex)
    // wrap and re-throw — but we lose n_ex_db, the caller now sees
    // a plain n_ex with no DB-specific fields
    throw f_make_ex("DB call failed: " + ex.getMessage())
end try
```

Where `f_make_ex(...)` returns a freshly constructed `n_ex` (the
base type), not a `n_ex_db`.

## Why it bites

PowerScript's exception hierarchy lets callers `catch` on a
specific subtype:

```pb
try
    ...
catch (n_ex_db db_ex)
    // handle DB-specific case — read db_ex.sqlcode, db_ex.sqlstate
catch (n_ex generic)
    // fallback
end try
```

This selectivity is the whole point of exception subtyping: a
caller can react to a DB failure differently from a generic
runtime failure.

When intermediate code does the pattern shown in the smell —
catches a subtype, then re-throws via a factory that constructs
the **base** type — the type information is destroyed. The
ultimate caller cannot tell whether the failure was a DB error
or anything else, because the exception that arrives is plain
`n_ex`. All the subtype-specific fields (`sqlcode`, `sqlstate`,
recovery flags) are gone too.

The bug is doubly painful because:

1. The author of the intermediate code usually thought they were
   "adding context" to the exception by wrapping the message.
   They were, in fact, destroying typing information that callers
   need.
2. The damage is invisible at the catch site — the code compiles
   and runs. It surfaces only when a caller tries to `catch
   (n_ex_db ...)` and the catch never fires because the
   exception was demoted upstream.

## Idiomatic fix

Re-throw the original exception (preserves type and all
sub-fields), and if you need to add context, mutate the existing
exception or chain via a "caused-by" field:

```pb
try
    iuo_db.exec_sql(ls_sql)
catch (n_ex_db ex)
    // option A — just re-throw, preserves n_ex_db and all its data
    throw ex
end try
```

Or, if you genuinely want to wrap (e.g. cross an API boundary
where the inner type is private):

```pb
try
    iuo_internal.process(...)
catch (n_ex_internal inner)
    n_ex_public outer
    outer = create n_ex_public
    outer.setMessage("public message")
    outer.cause = inner   // chain, don't drop
    throw outer
end try
```

Reserve the wrap pattern for the cases where the inner type is
genuinely private to a module. For the common "add context"
case, `throw ex` (after mutating `ex.message` if you must) is
the correct idiom.

In code review, search for `catch (n_<subtype> <var>) ... throw
<call>(` patterns and verify the `<call>` returns the same
subtype as `<subtype>`. If it returns the base type, flag it.

## Where it has been seen

- The logging chain of a private PB framework (review run
  2026-05-20): the DB-aware log target wrapped every DB exception
  it caught into the framework's plain base exception via a
  factory. Callers further up could not distinguish DB failures
  from other logger failures, and ended up retrying the operation
  indiscriminately.

## Related

- (no siblings yet — first exception-handling antipattern in the
  catalog)
