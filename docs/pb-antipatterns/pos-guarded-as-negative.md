# `Pos()` guarded against a negative it never returns

## Smell

```pb
int left
string result

left = pos (sParseString, sToken)

/* the token is not present in the message */
if left < 0 then return ""

left = left + len(sToken)
right = pos (sParseString, la, left)
result = mid (sParseString, left, right - left)
```

## Why it bites

PowerScript's string-search functions return **0** when they find
nothing. Never `-1`, never anything negative. From the Appeon
PowerScript reference for `Pos`: *"If string2 is not found in string1
or if start is not within string1, Pos returns 0. If any argument's
value is null, Pos returns null."*
(<https://docs.appeon.com/pb2022r3/powerscript_reference/pos_func.html>)

So `if left < 0` is dead code, and the not-found case does not return
early — it falls straight through with `left = 0` into arithmetic that
assumes a real position. The function then reads from an offset it
invented and returns a plausible-looking string.

Two properties make this worse than an ordinary off-by-one:

- **It fails in the safe-looking direction.** The guard reads as
  defensive programming. A reviewer skims it, sees the comment above it
  stating the intent correctly, and moves on. The code behaves exactly
  as if the guard had never been written.
- **The wrong answer is not obviously wrong.** A missing token produces
  an empty string only by luck; the usual outcome is a substring of the
  input, which downstream code treats as a table name, a column name or
  an identifier.

The null case compounds it. If either argument is null, `Pos` returns
null, and a comparison against null yields null rather than true — so
the `then` branch is not taken there either.

The habit is imported. `indexOf` in Java, C# and JavaScript, `strpos`
conventions in C, and `String.IndexOf` in .NET all use `-1` for
not-found; PowerScript uses 0, and it uses 0 consistently across `Pos`,
`LastPos` and `Match`.

## Idiomatic fix

Test the sentinel the language actually uses:

```pb
long left

left = pos (sParseString, sToken)

if left <= 0 then return ""
```

`<= 0` rather than `= 0` costs nothing and also absorbs the null case
in the direction you want. Prefer `long` over `int` for the result
while you are there — `Pos` and `Len` return `long`, and a PB `integer`
truncates silently above 32 767.

## How to find it

Grep alone is not enough, and that is worth knowing before concluding a
codebase is clean. The direct form is easy:

```
grep -rniE '(pos|lastpos) *\(.*\) *(< *0|= *-1)'
```

but the dangerous form assigns to a local on one line and compares on
another, so it needs a scan that tracks which variables were assigned
from `Pos`/`LastPos` and then compares them against `< 0` or `= -1`
within a short window. In the case below, the direct grep returned
nothing and the variable-tracking scan found the bug.

## Where it has been seen

- A warehouse-management framework's database-error parser (review run
  2026-08-12): `parser()` extracted table and constraint names out of
  SQL Server trigger messages, guarding with `if left < 0`. The values
  fed the error codes shown to operators, so an unexpected message
  shape produced a wrong table name in a user-facing error rather than
  an empty one. Scanning all **2426** `.sr*` sources in that workspace
  found this as the **only** occurrence — the codebase otherwise writes
  `if Pos(...) = 0 then` consistently. The entry is here for the way it
  fails, not for how often it appears.

## Related

- [`isnull-on-numeric`](isnull-on-numeric.md) — the same root cause in a
  different costume: a sentinel convention carried over from another
  language, producing a guard that never fires.
- [`fileopen-unchecked`](fileopen-unchecked.md) — sentinel returns that
  are not checked at all, rather than checked against the wrong value.
