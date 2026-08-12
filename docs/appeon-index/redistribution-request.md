# Asking Appeon to let the doc index be redistributed

**Status: draft, not sent.** Written 2026-08-12 for Carlo Torrese to put to
Armeen Mazda, CEO of Appeon, in person at a PowerBuilder event in Italy in
October 2026. Nothing here has been agreed with Appeon, and until it is, the
kit keeps building the index locally on each machine and redistributes
nothing.

## What we are asking permission for, in one sentence

Permission to attach the **built search index** — a SQLite database derived
from the publicly readable PowerScript reference on `docs.appeon.com` — to
releases of the open-source [`pb-ai-code`](https://github.com/restoresrl/pb-ai-code)
repository, so that a PowerBuilder developer gets it in one command instead of
re-scraping the documentation site themselves.

## Why permission is needed at all

The documentation is free to read: no paywall, no login, and
`docs.appeon.com` publishes no `robots.txt` and no terms-of-use notice on the
pages themselves. But the manuals carry an explicit notice, and it is
unambiguous. From the copyright page of the *Users Guide for PowerBuilder*:

> Copyright © 2019 Appeon. All rights reserved. […] No part of this
> publication may be reproduced, transmitted, or translated in any form or by
> any means, electronic, mechanical, manual, optical, or otherwise, without
> the prior written permission of Appeon Inc.

"Reproduced, transmitted […] electronic" covers a database file attached to a
GitHub release. So the answer is not to interpret the clause creatively; it is
to ask for the written permission the clause itself contemplates.

## The short version — for a conversation, not a document

> We maintain a free, open-source toolkit that lets AI coding assistants work
> on PowerBuilder codebases. One piece of it makes the assistant look up the
> official PowerScript reference instead of guessing: it ingests the public
> documentation into a small local search index, and every answer it gives
> cites the `docs.appeon.com` URL it came from.
>
> Today each developer builds that index by crawling your documentation site
> themselves — about 1,300 pages, once per machine. We would rather build it
> once and attach it to our public releases, which means **your site gets
> crawled once instead of once per user**. That needs your written permission,
> because the manuals reserve reproduction rights, and we would rather ask
> than assume.
>
> We are happy to bound it however you prefer: named versions only,
> attribution and your copyright notice carried in the file, every answer
> citing the canonical URL, refreshed from the live site rather than frozen,
> and withdrawn immediately if you ever want it withdrawn.

## What the thing actually is

Precise, because a vague description invites a cautious no.

| | |
| --- | --- |
| Source | `https://docs.appeon.com/pb2022r3/powerscript_reference/` — the section currently configured |
| Size | 1,292 pages, one PB version, producing a 4.5 MB SQLite file |
| Crawl behaviour | 200 ms between requests to the same host, conditional GET so a refresh re-fetches only what changed |
| Contents per page | name, category, entry kind, description, syntax, arguments, return value, examples, "see also", and the **source URL** |
| How it is used | four read-only MCP tools — search, get, list topics, list versions — called by an AI assistant during a code review |
| Not included | anything behind a login, anything from the product itself, any customer code |
| Licence of the toolkit | MIT. The index would ship under whatever terms Appeon sets, stated separately from the code |

It is a **machine index, not a mirror**. There is no browsable copy of the
documentation, no HTML, no site. A human cannot read it without writing SQL;
an assistant queries it for one entry at a time and shows the user the
official link.

## What Appeon gets

Stated plainly, including the part that is self-interested.

- **Less crawling, not more.** Today, every developer who installs the kit
  fetches ~1,300 pages from your servers. With a release asset, that happens
  once, by us, and everyone else downloads a file from GitHub. The request is
  for permission to *reduce* the load our users put on your site.
- **Every AI answer points back to your documentation.** The tools return the
  canonical `docs.appeon.com` URL with every result, and the toolkit's rules
  require an assistant to cite it rather than assert PowerScript behaviour
  from memory. The alternative is not silence — it is an assistant that
  guesses, confidently and wrongly, and attaches a code change to the guess.
- **PowerBuilder becomes usable with the tooling developers now expect.** The
  audience is people maintaining decades-old PB monoliths who are being asked
  why their stack cannot be worked on the way everything else is. This is a
  retention story, and it costs Appeon nothing.
- **It comes from the community.** The request is being made by the president
  of AUGI, the Italian Appeon User Group, on behalf of an initiative that is
  free, open, and aimed squarely at existing PowerBuilder customers.

## Safeguards we are offering up front

Not concessions extracted later — the shape we would prefer anyway.

1. **Attribution.** The Appeon copyright notice travels with the file and is
   stated in the repository and in the release notes.
2. **Every answer cites the source.** Already true; we will keep it true.
3. **Scope by agreement.** Only the versions and sections Appeon names. Today
   that is one version and one section.
4. **Freshness, not a fork.** The index is rebuilt from the live site; it is
   never edited, and corrections belong upstream in your documentation.
5. **Immediate withdrawal.** One message and the asset comes down, with no
   argument and no notice period.
6. **No human-facing mirror.** We will not publish a readable copy of the
   documentation, in any form, at any time.
7. **Whatever paperwork suits you.** A licence grant, a letter, or a line in
   an email — whatever Appeon's counsel prefers.

## If the full answer is no: a narrower ask

Copyright protects expression, not facts. A **facts-only index** would carry,
per entry, the name, the argument names and types, the return type, the entry
kind, and the URL — and none of the descriptive prose or examples.

That is much closer to a table of contents than to a reproduction of the
manual, it still answers most of what an assistant needs during a code review,
and the descriptive text stays where it belongs: on `docs.appeon.com`, fetched
live when a question genuinely turns on the wording.

We would rather ship the full index. We would take this happily.

## What we would like to come away with

In order of preference:

1. Written permission to redistribute the built index, on the terms above.
2. Written permission for the facts-only index.
3. A clear "no", which is also a useful answer — it settles the question and
   the kit keeps building locally, which is what it does today.

There is also a smaller thing worth confirming while the subject is open:
**that the local scraping itself is fine.** It is what every user does now, it
is polite and cached, and no notice on the site forbids it — but if Appeon
sees it differently, we would rather hear that from you than assume.

## Practical notes for the conversation

- The repository is public: <https://github.com/restoresrl/pb-ai-code>. The
  index code is under `tools/pb-appeon-index/`, and what it collects is
  visible there in about 400 lines.
- The database is **not** in the repository today and never has been. It is
  gitignored, and the toolkit's own documentation says it is built locally and
  not redistributed.
- Nothing changes on our side while the question is open. This is a request
  for permission, not a notification of intent.
