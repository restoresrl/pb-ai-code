# An exception factory called in statement position

## Smell

```pb
ds_target.create(ls_syntax, ls_err)
if ls_err <> "" then f_make_ex("n_ex", ls_err)     // builds it, drops it
```

Where `f_make_ex(...)` is a global function that **returns** a freshly
constructed exception object. Nothing is raised. The statement builds an
exception, discards it, and execution continues.

## Why it bites

Three things line up to make this invisible.

**PowerScript lets you discard a return value.** A function call is a
legal expression statement, so `f_make_ex(...)` on its own compiles
without a warning. There is nothing for the compiler to object to.

**The factory reads like a verb.** Exception factories tend to get short
names — `ex(...)`, `err(...)`, `fail(...)` — precisely because they are
called constantly, and a short name in statement position reads as an
imperative. `if ls_err <> "" then ex("n_ex", ls_err)` looks like *"if
there was an error, raise it"*. It is not; the only difference between
that line and the correct one is the word `throw`.

**The failure surfaces far away.** The function does not stop. It
carries on with whatever half-initialized state the error was reporting,
and typically returns success, so the caller has no signal either. What
eventually fails is something downstream that depended on the state
being valid — in a different object, with a different message, long
after the real cause is unrecoverable.

It is the same family as
[`throw-factory-loses-subtype`](throw-factory-loses-subtype.md): both
are a factory returning an exception object, and both damage error
handling in a way the code's shape conceals. That one loses the *type*;
this one loses the *raise*.

## Idiomatic fix

```pb
ds_target.create(ls_syntax, ls_err)
if ls_err <> "" then throw f_make_ex("n_ex", ls_err)
```

If the factory is used often enough that the omission keeps happening,
consider a second global that raises rather than returns — `f_throw_ex`
— so the call site says what it does and the returning form is reserved
for the cases that genuinely need the object first (chaining a cause,
attaching fields before raising).

## How to find it

This one is worth a mechanical sweep, because reading does not catch it:
the wrong line and the right line differ by one word and the wrong one
is the shorter, more idiomatic-looking of the two.

Find every call to the factory that is **neither** the operand of a
`throw` **nor** the right-hand side of an assignment:

```
grep -rnE '(^|[^a-z_])(ex|f_make_ex)[[:space:]]*\(' --include='*.sr*' .
```

then discard the hits preceded by `throw` or containing `=` before the
call. What is left is either a bug or a deliberate construct-then-raise
that should be assigning to a variable anyway.

## Where it has been seen

- The `init()` of a persistence base class in a warehouse-management
  framework (review run 2026-08-12). The class builds its DataWindow at
  runtime when no hand-made one exists — the path every newer object
  takes — and on failure did `if err <> "" then ex("n_ex", err)`. The
  syntax error was discarded, the datastore was initialized anyway, and
  `init()` returned TRUE. The class had **149 descendants**.

  The same file gets it right twice, a few hundred lines away, in the
  form `if res <> "" then throw ex("runtimeerror", res)` — so the
  convention was established and this was a dropped keyword, not a
  misunderstanding.

  The downstream symptom is worth recording because it is what somebody
  would actually be debugging: with no valid DataWindow, a later
  `Describe("datawindow.table.updatetable")` returns `"!"`, which is
  concatenated into a WHERE clause and reaches the database as a syntax
  error about a table named `!`.

## Related

- [`throw-factory-loses-subtype`](throw-factory-loses-subtype.md) — the
  sibling: an exception that *is* raised, but demoted to its base type on
  the way.
