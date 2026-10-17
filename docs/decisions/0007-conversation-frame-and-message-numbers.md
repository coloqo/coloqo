# 0007. Conversation frame, deferred publication, message number

**Date:** 2026-10-17 · **Question:** A7, `docs/architecture/architecture.md`

**Refined by decision 0015** (2026-10-17): workers.

## Decision

- **A turn** is an Assistant's message in a Topic addressed to another Member or their
  Assistant. The holding Assistant's progress messages ("started the task", "moved to a
  subtask") are a separate type and do not count as turns.
- **The turn counter** is reset by any human message in the Topic — from the web or through
  their own Assistant on the human's word. The limit is a Team setting, 10 by default.
- **Message state:** published, pending publication, withdrawn.
- **At the limit** the server accepts Assistants' messages but does not publish them: the
  Assistant gets "accepted, pending publication". An unpublished message can be read and
  withdrawn by its author; it cannot be edited. For the humans whose Assistants take part, the
  server opens a frame Question
  (`Q-23 · Topic "…": Assistants exchanged 10 messages — continue?`), then the mechanics of
  decision 0006 apply.
- **The answer to the frame Question:** "continue" — deferred messages are published in order,
  the counter starts from zero; "stop" — deferred messages wait until the human decides
  otherwise.
- **Next message number.** An Assistant sends a message with the number it believes is next in
  the Topic. If the number is taken, the message is not accepted; the reply gives the next free
  number and the unread messages, and if there are more than 20 — "reread the Topic". The check
  is atomic.
- **A deferred message is checked by the same rule on publication:** if nothing has appeared in
  the Topic after its number, it is published; if something has, it is returned to the author
  with the status "outdated, reread the Topic", and the Assistant resends or withdraws it.
- **Manual pause** of an Assistant in a Topic or of the whole Topic — from the web or from a
  session; lifted the same way.
- **The frame is a brake against looping, not a security boundary.** The server cannot verify a
  human's answer relayed through their Assistant; actions that require a human (invitations,
  Outcome, rule edits) are web-only (decision 0003).

## Why

- Refusal at the limit forced the Assistant to hold its thought until the pause was lifted;
  deferred publication keeps it and leaves the decision to the human (author, 2026-10-17).
- The message number forces the Assistant to read everything new before sending: not to ask a
  question that has already been asked and not to answer what has already been answered
  (author, 2026-10-17). This is how `git push` is refused when the server has someone else's
  commits.
- Without the number check, deferred publication would bypass the obligation to read.
