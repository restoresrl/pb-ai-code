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

**Design phase**. Nessuno scaffolding tecnico ancora. La visione,
decisioni prese e decisioni residue sono in [`PLAN.md`](PLAN.md).

Sequencing: il lavoro vero parte **dopo** che `pb-orca-mcp` è pubblicato
su PyPI (currently `v0.1.0`, target dipendenza `pb-orca-mcp>=0.1.0`).

Vedi [`PLAN.md`](PLAN.md) → "Sequencing" per i 5 TODO che precedono
l'attivazione di questo repo.

## Stack & convenzioni (previsti)

Le convenzioni concrete verranno fissate quando partirà lo scaffolding.
Linee guida sintetiche per coerenza con `pb-orca-mcp`:

- Se ci sarà codice Python: Python 3.10+, `from __future__ import annotations`,
  type hints, `mypy --strict`, `ruff` line-length 100, src-layout,
  `hatchling`.
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
  i source PB sono UTF-16 LE BOM + CRLF. Edit/Write su questi file li
  flippa a UTF-8 BOM e PB li rifiuta. Riconvertire con
  `[System.Text.Encoding]::Unicode` in PowerShell.
- **Git**: mai `git commit` / `git push` senza conferma esplicita di
  Carlo (eredita regola CLAUDE.md root).
