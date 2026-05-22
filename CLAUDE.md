# CLAUDE.md — pb-ai-code

Istruzioni locali al progetto. **Lingua di lavoro: italiano** (codice e
doc utente in inglese, audience internazionale). Se esiste un `CLAUDE.md`
parent (workspace-level), questo lo estende con le specificità del dev
kit agentico.

## Contesto

`pb-ai-code` è il **dev kit agentico per PowerBuilder**: insieme di
skill, documentazione Appeon ingestita (mix mirror + WebFetch),
orchestrazione di test, pattern di debug post-mortem e slash command,
pensati per abilitare un coding agent (Claude Code in primis) a fare
**progettazione, coding, testing e debugging** completi su PB.

È il **livello sopra `pb-orca-mcp`** (sibling, `../pb-orca-mcp/`): non
duplica nessuna primitive ORCA. Ogni azione sul `.pbl` passa attraverso
i tool MCP di `pb-orca-mcp`.

**Audience**: chiunque sviluppi PB e voglia un workflow agentico. Nessun
riferimento Restore-internal nel codice o nei doc.

## Stato

**Dogfooding interno + refactoring-first**. Il dev kit ha consolidato
Pillar 1-scaffolding (skill `pb-scaffold` + 6 pagine Layer 2 seeded,
pushato 2026-05-19) e ha riprioritizzato il backlog il 2026-05-19 sera
verso un uso primario di **code-review per refactoring di legacy
PB** — vedi sezione "Re-prioritization 2026-05-19" di [`PLAN.md`](PLAN.md).

In pratica, il prossimo slice di lavoro è:

1. Skill `pb-context-build` — scoping intelligente del context per
   workspace PB monolitici.
2. Slash command `/pb-review` (Phase A, report-only).
3. Validazione end-to-end su un target Magware piccolo.
4. Skill `pb-impact-analysis` come pre-flight di refactor.

Testing (Pillar 2) e runtime trace logging restano rimandati. Il
sequencing originale 2026-05-14 (4 pillar peso bilanciato) è
sostituito dal modello a 3-tier.

**Dipendenza**: `pb-orca-mcp` è MCP server raggiungibile via
`.mcp.json` (wiring x86 risolto 2026-05-19 puntando a
`../pb-orca-mcp/.venv-x86/`). Non importato come libreria Python —
`pyproject.toml` di pb-ai-code non lo lista come dep.

Vedi [`PLAN.md`](PLAN.md) → "Re-prioritization 2026-05-19" e "Next
slice" per il quadro completo.

## Stack & convenzioni (previsti)

Le convenzioni concrete verranno fissate quando partirà lo scaffolding.
Linee guida sintetiche per coerenza con `pb-orca-mcp`:

- Se ci sarà codice Python: Python 3.10+, `from __future__ import annotations`,
  type hints, `mypy --strict`, `ruff` line-length 100, src-layout,
  `hatchling`. Dipendenza `pb-orca-mcp` da `pyproject.toml` punta in
  editable install al sibling locale durante la fase corrente; sarà
  riportata a `pb-orca-mcp>=0.1.0` quando si pubblica.
- Skill in `.claude/skills/<name>/SKILL.md` (formato Claude Code standard).
- Slash command in `.claude/commands/<name>.md`.
- Docs Appeon mirrorate sotto `docs/appeon/` (struttura TBD,
  attribution/licenza da verificare).
- Test (se Python): pytest. Test PB veri: i `requires_pb` vivono in
  `pb-orca-mcp`, non qui (qui sono test di skill / parsing / orchestrazione).
- Lingue: codice + commit + doc utente in **inglese**; conversazione
  con Carlo in **italiano**.
- Niente trailer `Co-Authored-By:` nei commit (preferenza Carlo).

## Cosa NON fare

- **Niente sintassi PowerBuilder qui dentro**. Questo è un repo di
  *workflow + knowledge + orchestrazione*, non un repo PB. Eventuali
  snippet PB nelle skill/doc sono illustrativi, non eseguibili.
- **Niente reimplementazione di primitive ORCA**. Se serve qualcosa che
  l'MCP non espone, va aggiunto in `pb-orca-mcp` (sibling), non qui.
- **Niente assunzioni sul workspace dello sviluppatore**. Skill e tool
  devono funzionare su qualsiasi macchina Windows con PB IDE + Claude
  Code. Niente path hardcoded utente-specifici.
- **Niente riferimenti Restore-internal**: no `magware/`, `mw21r2`,
  `rstpb22`, path personali Carlo, customizzazioni Magware. Il
  *pattern* (es. logging stile `n_logger`) può essere ispirazione, ma
  va riformulato in modo vendor-neutral.
- **Niente dipendenze dirette da repo Restore**. La dipendenza unica
  esterna è `pb-orca-mcp` come libreria PyPI pubblica.

## Riferimenti

- [`PLAN.md`](PLAN.md) — design doc completo: visione 4-pilastri,
  decisioni prese, decisioni residue, sequencing, out-of-scope.
- Sibling project `pb-orca-mcp`: `../pb-orca-mcp/` (locale),
  `https://github.com/restoresrl/pb-orca-mcp` (remoto).
- Appeon PB docs: https://docs.appeon.com/

## Workflow di sviluppo (per quando partirà davvero)

- **Restart strategy** (eredita da `pb-orca-mcp/CLAUDE.md`): se sarà
  necessario un restart di Claude Code, usare `claude --resume` / `-c`
  per preservare il transcript. Handoff memory solo come fallback per
  sessioni "sporche" o context near-limit.
- **Encoding caveat per `.sr*`** (se le skill toccano file PB di test):
  l'encoding dei file in `ws_objects/<lib>.pbl.src/` è quello indicato
  dalla direttiva `DefaultExportEncode` del `.pbw` del workspace. PB
  2022 accetta tre valori: `"UTF-8"` (BOM + CRLF), `"UTF-16BOM"`
  (UTF-16 LE BOM + CRLF), `"ANSI"` (codepage di sistema + CRLF). Tutti
  i workspace Restore surveyati (rstpb22, pbgettext22, pbunit22,
  mw21r2 e le 11 customizzazioni Magware) usano oggi `"UTF-8"`. In
  lettura PB rileva l'encoding via BOM detection, quindi è tollerante;
  in scrittura conta matchare l'encoding del `.pbw` per evitare un
  cascade di Refresh + Regenerate sul prossimo open dell'entry in IDE.
  Il tool MCP `pb_edit_and_import` accetta un parametro `source_encoding`
  con questi 3 valori (default `"UTF-8"`) — leggere `DefaultExportEncode`
  dal `.pbw` e passarlo esplicitamente. Sui comment multi-riga: il tool
  normalizza ogni stile di newline (CRLF / LF / CR) a CRLF prima di
  storare nel `.pbl` e prima dell'escape PowerScript (`~r~n`). Senza
  questa normalizzazione i comment multi-riga apparirebbero come
  singola riga nel Library Painter Properties dialog di PB IDE — il
  textbox Windows renderizza solo `\r\n` come line break visibile.
- **Git**: mai `git commit` / `git push` senza conferma esplicita di
  Carlo (eredita regola CLAUDE.md root).
