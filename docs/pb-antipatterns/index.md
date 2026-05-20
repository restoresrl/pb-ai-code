# PowerScript antipattern catalog

A growing reference of recurring bugs and dangerous idioms in
PowerBuilder code. Each entry documents one antipattern: the
"smell" (a small code sample showing what's wrong), why it bites,
the idiomatic fix, and (when known) historical examples of
real-world incidents.

The catalog is meant to be consulted by `/pb-review` during the
**bug-risk** pass of Step 2b. The agent should walk the entries in
the context pack looking for matches against these patterns before
deciding a code chunk is clean.

The catalog grows **on encounter**: when a reviewer (human or
agent) finds a new pattern that isn't here, it gets added. Do not
seed speculative entries — every entry should reference at least
one concrete case where it bit.

## Entries

### Memory management

- [destroy on auto-instance shadowing](destroy-on-auto-instance.md) —
  `destroy <name>` distrugge il global auto-instance, non il field
  privato omonimo.
- [exitprocess in destruction chain](exitprocess-in-destruction.md) —
  `exitprocess(...)` chiude il processo, non distrugge l'oggetto.

### Type system

- [isnull on numeric types](isnull-on-numeric.md) — `IsNull()` su
  `integer`/`long`/`ulong` ritorna sempre `false`, anche su
  sentinel `-1` wrappato.

### IO

- [space() with uninitialized buffer length](space-before-init.md) —
  pattern Win32 W-suffix dove `space(buffer_len)` viene chiamato
  prima che la DLL abbia riempito `buffer_len`.
- [unchecked fileopen() return](fileopen-unchecked.md) —
  `filewrite` su handle `-1` fallisce silenziosamente.

### Exception handling

- [throw factory loses subtype](throw-factory-loses-subtype.md) —
  `catch (n_X ex) ... throw f_make_ex(...)` perde la sottoclasse
  specifica di `ex`; usare `throw ex` per ri-lanciare preservando
  il type concreto.

## How to add a new entry

1. Create `docs/pb-antipatterns/<slug>.md` with the sections
   below.
2. Add a link to the relevant category in this `index.md`.
3. If the new entry surfaces a category not yet covered (e.g.
   concurrency, SQL injection, deprecated API usage), open a new
   section here.

### Per-entry template

```markdown
# <title — short, descriptive>

## Smell

<minimal code sample showing the antipattern, in a ```pb fence>

## Why it bites

<one-paragraph explanation of the bug or hazard. Cite PB
semantics, runtime behavior, or Appeon docs where relevant.>

## Idiomatic fix

<code sample showing the corrected pattern, in a ```pb fence.
Explain in 1-2 lines why this works.>

## Where it has been seen

<one or two short bullets: project, date or commit, brief context.
Anonymize if needed but keep it concrete.>

## Related

<links to other antipatterns in the catalog that share root cause,
e.g. same misunderstanding of PB semantics>
```

## Cross-references

- [`/pb-review`](../../.claude/commands/pb-review.md) — Step 2b
  consults this catalog during the bug-risk pass.
- [`pb-src-format`](../pb-source-format/) — sibling reference for
  the on-disk layout of `.sr*` files.
- [`appeon-query`](../../.claude/skills/appeon-query/SKILL.md) —
  when the antipattern hinges on a specific PowerScript function
  or runtime behavior, link to the Appeon doc via this skill.
