# 0005. A secret is transferred on request

**Date:** 2026-10-16 · **Question:** A5, `docs/architecture/architecture.md`

## Decision

- **Three steps; delays between them do not matter.**
  1. The recipient requests the secret; the request carries their one-time Diffie — Hellman
     public part, signed with their installation key (decision 0004).
  2. The sender verifies the signature, creates their own one-time part, derives the agreement
     key, encrypts and puts the ciphertext together with their public part, signed with their
     installation key.
  3. The recipient verifies the signature, derives the same key and decrypts.
- **The private half waits in the plugin.** The recipient's plugin keeps it in its local
  storage, not in session memory, and erases it after decryption. Decryption is done by the
  installation the request was sent from.
- **Without a request — through an offer.** The sender writes "I have a secret for you", the
  recipient's Assistant answers with a request, then the same three steps follow.
- **Several recipients** — each with their own request and their own ciphertext.
- **File encryption** — streaming, with a ready, proven scheme rather than our own; the scheme
  is chosen at implementation.
- **Ciphertext storage** (the flag from the product statement, question 8): "until received" —
  on the server's disk until it is fetched, a day by default, no longer than a week, the sender
  chooses the term; "no storage" — only in server memory, until received or 15 minutes. After
  receipt the ciphertext is deleted.
- **Transfer states:** not sent, awaiting receipt, received, expired.

## Why

- The request itself carries the recipient's public part, so the sender encrypts right away and
  the recipient does not need to be online at the same time (author's proposal, 2026-10-16).
- The server needs no store of keys published in advance, and the plugin does not need to
  replenish one: a transfer without a request costs one extra message.
- One-time parts: a later leak of an installation key does not reveal past transfers.
