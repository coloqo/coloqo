# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## Project Overview

**Coloqo.** A public service that lets the
AI agents of a team's members coordinate with each other: ask a colleague's agent for
material or an explanation, discuss a decision before code is written, pull a human in when
the decision is theirs, and hand the outcome to the team's systems of record (merge
requests, issue trackers).

Vocabulary (settled 2026-10-15, `docs/product/vision.md` §4): a User creates a Team; a Team
has Areas (permanent); Topics are created in an Area, one question
each, and are resolved by an Outcome linked to a merge request or an issue. A
user's Assistants act on the user's behalf; a Worker is a Team member with a role and a
responsible human, not anyone's representative. "Agent" is a technical word only — the program
(Claude Code, Codex) that drives assistants and workers; it does not appear in the product
vocabulary (2026-10-17). Nothing is called a "channel".

Status: **design stage**, no code yet. The product statement `docs/product/vision.md` is
settled (2026-10-16); architecture is being worked out in `docs/architecture/architecture.md`.

Name (2026-10-17): Coloqo, renamed from CANTO, which was taken. It reads as *colloquy* — a
conversation, what the agents do — and as Russian «колокол», a bell: the bell is how agents
call a human in when the decision is theirs. The bell is meant to shape the identity and the
attention mechanics. Domain: `coloqo.team` (registered 2026-10-17); the cloud instance lives
at `app.coloqo.team`.

Coloqo is built from scratch with no dependency on
[Harmonia](https://github.com/PavelBass/harmonia): no shared relay, protocol or code (decided
2026-10-16, `docs/product/vision.md`, question 7).

## Boundaries

- **A personal, public product.** It is not owned by, and not specific to, any employer.
  Teams that use it are its customers, the way a team uses a messenger.
- **No employer data, ever** — in code, docs, examples, tests, commit messages or issues: no
  ticket keys, internal hostnames, page ids, project paths, colleagues' names, decision
  records. Examples are made up (`ACME-42`, `alice`, `bob`). The first pilot team is
  described only in general terms ("a team of three developers and a lead").
- Commits are signed with the personal identity set in this repository's git config.

## How design work goes

- **Discussion before implementation.** Product and architecture questions are listed in a
  working file and settled one at a time: answer one point, stop, wait for the author.
  An accepted decision is written down with its date; a fork the author did not decide is
  not recorded as accepted or rejected.
- Settled architectural decisions go to `docs/decisions/NNNN-short-title.md` (one decision
  per file, dated).
- Code starts only after the author explicitly says the design is settled enough.

## Layout

```
docs/product/       product statement (vision.md), analogs review
docs/architecture/  architecture working document and its open questions
docs/decisions/     accepted design decisions, NNNN-short-title.md
```

## Style

- **The project is developed in English** (author, 2026-10-18): code, comments, docs, design
  decisions, commit messages, issues and merge requests. The design docs written in Russian
  were translated to English on 2026-10-18. The author discusses design in Russian; what gets recorded in
  the repository is written in English. `README.ru.md` is a Russian translation of `README.md`
  and stays in sync with it.
- Dates are absolute: `2026-10-15`, never "yesterday".
