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
seed speculative entries: every entry should reference at least
one concrete case where it bit.

## Entries

### Memory management

- [destroy on auto-instance shadowing](destroy-on-auto-instance.md):
  `destroy <name>` distrugge il global auto-instance, non il field
  privato omonimo.
- [exitprocess in destruction chain](exitprocess-in-destruction.md):
  `exitprocess(...)` chiude il processo, non distrugge l'oggetto.

### Type system

- [isnull on numeric types](isnull-on-numeric.md): `IsNull()` su
  `integer`/`long`/`ulong` ritorna sempre `false`, anche su
  sentinel `-1` wrappato.
- [pos guarded as negative](pos-guarded-as-negative.md): `Pos()`
  torna **0** quando non trova, mai `-1`: la guardia `< 0` è morta e
  il caso "non trovato" prosegue con un offset inventato.

### Process and control flow

- [halt in a shared library](halt-in-shared-library.md):
  `MessageBox` / `HALT CLOSE` dentro una `.pbl` che anche un target
  headless carica: il servizio si pianta su un modale che nessuno vede,
  o si spegne in silenzio.

### IO

- [space() with uninitialized buffer length](space-before-init.md):
  pattern Win32 W-suffix dove `space(buffer_len)` viene chiamato
  prima che la DLL abbia riempito `buffer_len`.
- [unchecked fileopen() return](fileopen-unchecked.md):
  `filewrite` su handle `-1` fallisce silenziosamente.

### Exception handling

- [throw factory loses subtype](throw-factory-loses-subtype.md):
  `catch (n_X ex) ... throw f_make_ex(...)` perde la sottoclasse
  specifica di `ex`; usare `throw ex` per ri-lanciare preservando
  il type concreto.
- [exception factory not thrown](exception-factory-not-thrown.md):
  `if err <> "" then f_make_ex(...)`: l'eccezione viene costruita e
  scartata. Manca `throw`, il compilatore non ha nulla da dire, e la
  riga si legge come gestione dell'errore.

### SQL and data access

- [DisableBind defeats bind variables](disablebind-defeats-bind-variables.md):
  `DisableBind=1` nel DBParm fa sì che PB inlinei i valori nel testo
  SQL: `:name` resta la sintassi che tutti riconoscono come sicura, ma
  non è più un bind. Il flag sta due classi più su, lontano da ogni
  statement.

## How a new entry gets here

Two routes. Directly, when you are working in this repository: the
template below. Or as a **note**, when the hazard turned up while working
on somebody's PowerBuilder library: the installed copy of this catalog is
a snapshot, so an addition made there is discarded by the next install.
`pb-review` writes such a discovery into the plan file's
`## Notes for the wiki` section, and [`wiki-notes.md`](../wiki-notes.md)
covers what happens to it.

## How to add a new entry

1. Create `docs/pb-antipatterns/<slug>.md` with the sections below.
2. Add a link to the relevant category in this `index.md`.
3. If the new entry surfaces a category not yet covered (e.g.
   concurrency, SQL injection, deprecated API usage), open a new
   section here.

> **Reading this from an installed bundle?** Then you are in a snapshot (`<harness>/pb-ai-code-docs/`), and the paths above do not exist here. Grow the catalog in the `pb-ai-code` repository and re-run the installer; an edit made in the snapshot is discarded by the next install.

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

- [`pb-review`](../../skills/pb-review/SKILL.md): Step 2b
  consults this catalog during the bug-risk pass. (Linked to the skill, not
  the `/pb-review` command: every install has the skills, while commands only
  exist for harnesses that have slash commands.)
- [`pb-src-format`](../pb-source-format/): sibling reference for
  the on-disk layout of `.sr*` files.
- [`appeon-query`](../../skills/appeon-query/SKILL.md):
  when the antipattern hinges on a specific PowerScript function
  or runtime behavior, link to the Appeon doc via this skill.
