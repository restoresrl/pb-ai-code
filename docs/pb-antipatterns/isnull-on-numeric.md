# `IsNull()` on a numeric type always returns `false`

## Smell

```pb
ulong lul_handle
lul_handle = OpenWin32Resource(...)

if IsNull(lul_handle) then
    // never executes, even when OpenWin32Resource returned a
    // sentinel "no value" via wraparound to -1 / 0xFFFFFFFF
    return -1
end if
```

## Why it bites

PowerScript's `IsNull()` checks the **null bit** of a variant
slot. For reference types and for variables that came from a SQL
fetch into a nullable column, the null bit can be set and
`IsNull()` returns `true`. For plain numeric locals (`int`,
`long`, `ulong`, `real`, `double`, `decimal`), the null bit is
not used at all — the slot always holds a numeric value, even if
that value happens to be `0` or `-1` or anything else.

So:

- A `ulong` that was assigned `-1` (which wraps to `0xFFFFFFFF`)
  is **not null**. `IsNull(lul_handle)` returns `false`.
- A `long` that was never explicitly assigned still holds `0`
  (the default). `IsNull(ll_count)` returns `false`.
- Only variables that carry a null bit from somewhere — a SQL
  `select ... into :var` of a nullable column, a `Dynamic Call`
  return of a method that returned null, or an explicit
  `SetNull(lvar)` — make `IsNull()` meaningful.

The bug pattern is treating `IsNull(numeric_local)` as a check for
"sentinel error value". It isn't. The error-value check has to be
against the actual sentinel:

```pb
if lul_handle = 0 or lul_handle = 4294967295 then ...
```

## Idiomatic fix

Check explicitly against the documented sentinel value of the API
or convention:

```pb
ulong lul_handle
const ulong INVALID_HANDLE = 4294967295   // 0xFFFFFFFF

lul_handle = OpenWin32Resource(...)

if lul_handle = INVALID_HANDLE or lul_handle = 0 then
    return -1
end if
```

For nullable SQL columns, fetch into a variable that carries the
null bit (PB does this automatically when the column is declared
nullable in the DBMS) and `IsNull()` works as expected:

```pb
long ll_optional_count
select count(*) into :ll_optional_count from foo where ...;

if sqlca.sqlcode <> 0 then
    return -1
end if

if IsNull(ll_optional_count) then  // genuinely null from DB
    ll_optional_count = 0
end if
```

In code review, treat any `IsNull(numeric_local)` as a red flag
and verify the variable was either set by a nullable SQL fetch or
explicitly null'd via `SetNull()`. If neither, the check is dead.

## Where it has been seen

- `rstpb22` (review run 2026-05-20): file handle defended with
  `IsNull(lul_handle)` after a Win32 wrapper that returned
  `0xFFFFFFFF` on failure; the guard never fired and the next
  write blew up downstream.

## Related

- [unchecked fileopen() return](fileopen-unchecked.md) — companion
  pattern: not checking the sentinel value of an IO handle.
