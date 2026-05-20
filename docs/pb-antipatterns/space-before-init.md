# `space(buffer_len)` called before `buffer_len` is set

## Smell

```pb
ulong  lul_buf_len
string ls_value

// pattern for Win32 W-suffix APIs that fill the buffer:
//   1) call once with NULL buffer to get required size
//   2) allocate the buffer
//   3) call again with the real buffer

// step 1 is missing, lul_buf_len is still 0
ls_value = space(lul_buf_len)
GetUserNameW(ls_value, lul_buf_len)
```

## Why it bites

The Win32 W-suffix (wide-char) API convention is two-call: the
first call passes a null buffer and gets back the required size
in the `LP*` argument; the second call passes a buffer of that
size and the API fills it. PB wrappers for these APIs faithfully
expose the convention.

If the developer skips the first call, `lul_buf_len` is still at
its default `0`, so `space(0)` returns an empty string. The
second API call then writes into a zero-length buffer — depending
on the API and the Windows kernel mood, this either:

- returns a "buffer too small" error code that the PB code
  forgets to check, or
- silently truncates to nothing, leaving `ls_value` empty, or
- (with some older APIs) corrupts adjacent memory.

The compiler does not flag it. The runtime does not flag it. The
PB IDE does not flag it. The bug only surfaces when the API in
question genuinely needs space — often a development machine
runs fine and a customer machine with a longer username does not.

## Idiomatic fix

Always implement the full two-call pattern when using a W-suffix
API:

```pb
ulong  lul_buf_len
string ls_value
long   ll_rc

// step 1 — ask for the size; PB passes "" (which the marshaller
// translates to a NULL pointer for the W call)
lul_buf_len = 0
ll_rc = GetUserNameW("", ref lul_buf_len)
// most APIs return ERROR_INSUFFICIENT_BUFFER here; check accordingly

// step 2 — allocate and call for real
ls_value = space(lul_buf_len)
ll_rc = GetUserNameW(ref ls_value, ref lul_buf_len)
if ll_rc = 0 then
    // genuine failure path
    return -1
end if
```

For APIs that don't follow the two-call convention, allocate a
fixed-size buffer with a documented upper bound (e.g.
`MAX_PATH = 260` for a path-returning API) and check the API's
own return-length value before consuming `ls_value`.

In code review, any `space(<variable>)` immediately followed by a
Win32 W call should be inspected for the missing first call.

## Where it has been seen

- `rstpb22` (review run 2026-05-20): a wrapper around a Win32
  W-suffix API allocated `space(buf_len)` with `buf_len` still at
  its default `0`. The wrapper "worked" in development because
  the test data happened to fit in the zero-length write (or
  silently dropped); customer-side runs with longer strings broke.

## Related

- [unchecked fileopen() return](fileopen-unchecked.md) — similar
  pattern of skipping a check on an IO-style return value.
- [isnull on numeric types](isnull-on-numeric.md) — same family
  ("Win32 sentinel value not properly guarded").
