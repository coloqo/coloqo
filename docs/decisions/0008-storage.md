# 0008. Storage

**Date:** 2026-10-17 · **Question:** A8, `docs/architecture/architecture.md`

**Refined by decision 0021** (2026-10-19): a closed Topic is kept for a week, then deleted down to its card.

## Decision

- **Database — PostgreSQL.** A relational model: Teams, Areas, Topics, messages, Questions,
  versioned rules, installations, Assistants.
  - The next message number check (decision 0007) is a unique key "Topic + number": the database
    rejects a repeated insert atomically.
  - The user-wide event sequence number (decision 0006) is a database sequence.
  - Fan-out of events to SSE streams — `LISTEN/NOTIFY`; there is one instance and no separate
    broker.
- **Files — on the server's disk, behind a storage interface.** For the pilot — a volume next to
  the database; the interface allows connecting S3-compatible storage later.
  - Non-secret files with long retention live as long as their Topic lives.
  - Ciphertext "until received" is deleted once all recipients have taken it, or on expiry
    (decision 0005).
  - "No retention" — only in process memory; a server restart loses it, and the transfer gets
    the state "expired".
- **Event log** — 7 days; to a client gone for longer the server answers "re-read the Inbox".
  The Inbox is state in the database, not the log.
- **Deletion.** The Team owner deletes a Topic or an Area for good — with its messages and
  files, after confirmation. Deleted data stays in backups until they expire (question A11);
  the terms of service say so.
- **Pilot limits** (settings): a file up to 100 MB, 5 GB per Team.

## Why

- The atomic number check, user-wide event numbering and event fan-out are covered by one
  database; with one instance a broker is unnecessary.
- Disk behind an interface is the simplest option for the pilot and does not rule out moving to
  object storage.
