# A message addressed to a person through one of their sessions misses the others

## What happened

2026-10-21, the pilot team, Coloqo 0.5.0; reported by one of the author's working sessions.

The author saw in the web new messages in a Topic, one of them addressed to them. None of their
sessions said so, although the watches of that project were running: three processes, all alive.

The message was bob's Assistant asking alice (the author) in which order to merge two MRs. It
answered a message alice's session `chime` had posted on their behalf, and addressed it to that
session: `to` was the full name `alice · project · chime`, so the message carries `to = alice`
and `to_assistant = chime`. alice was working in another session, `nunki`, and learned of the
message only at their next prompt, from the `UserPromptSubmit` hook. Whether `chime` was still
running is not known. bob's session stopped until alice answered.

## Facts checked (2026-10-21)

- **The sender chooses the session.** `post_message` takes as `to` a Member's pseudonym or an
  Assistant's full name; the server's `addressee` sets `to_assistant` only for a full name. Coloqo
  does not derive it from the thread (`reply_to`).
- **The watch's filter** (`describe` in `plugin/src/coloqo/watch.py`) shows a message to a session
  when it is addressed to that session (`to_assistant` is its own), or to its person with no
  session named, or when the session took part in the Topic and the message is addressed to
  nobody or to its person. A message to `alice` through `chime` passes for `chime` alone; every
  other session of alice drops it without a word. The focus does not matter: the filter runs
  before it, `all` included.
- **What still reaches alice:** the Inbox at a session's start lists it (the Inbox is per person,
  `addressed` is set for the person); the `UserPromptSubmit` hook mentions it at their next prompt,
  unless the session's focus is `quiet`; the web shows it. A session that is waiting or busy without
  a new prompt from them shows nothing.

## Why it is a gap

- The addressee is a person. `alice · chime` is alice, represented by `chime`; answering, the
  sender points at whom it talked to, not at which of alice's sessions should hear.
- Sessions are short and replace each other: they end, get compacted, take Topics over from each
  other (`hold_topic`). An answer that comes hours later usually finds the asking session gone.
- It hits hardest a question for a decision: exactly what is addressed to a person, with the
  sender waiting.

## Proposed (by the reporting session)

1. **A fallback when the session is away.** When `to_assistant` names a session that is not live,
   the event reaches the person's live sessions in that session's project, or in every project if
   none. No repeats while the addressed session is alive; needs a sign of a live session (the
   server already has one: `holder_live` in `topic_idle`, from `Assistant.last_seen_at`).
2. **Every session of the person.** A message to a person reaches all their live sessions whatever
   `to_assistant` says: "to you" in the addressed one, "to alice through chime" in the others.
   Simpler; a line in every open session.
3. **In any case:** the `UserPromptSubmit` hook and the Inbox tell a message addressed to the
   person through another session apart, so a session showing it does not take the question as
   its own and answer for another without the person.

The reporting session recommends 1.

## Decided

2026-10-21, the author:

- **A message to a session that is not online goes to its person,** at once, when it is sent.
  Online means the session's stream is open (`2026-10-21-which-assistants-are-live.md`); a session
  offline for a minute is offline. The message keeps a mark: it was meant for that session, which
  is offline. Every online session of the person sees it, with the mark ("meant for chime, which
  is offline"); with none online, it waits in the person's Inbox and in the web.
- **The sender is told** in the answer to its post who will get the message.
- **A message to an online session** goes to it, as now.
- **Weighed:** readdressing when the session is forgotten (20 minutes offline), as a periodic job.
  Dropped: the person would learn of the message 20 minutes late, and nothing needs to wait.
- **`post_message`** tells assistants to address the person by default, and a session only when
  the question is about that session's own work.
- **A message to an online session is seen by the person's other online sessions too,** as a quiet
  line: "a message for chime from mirach in T-12; chime answers it". The person learns there is a
  question and where; the assistant there knows it is not its own and does not answer for another
  session. The session's focus filters the line as any event (`mine` does not show it).
- **The prompt hook and the Inbox** mark a message addressed to the person through another session
  the same way.

## How to check

1. Session A of a person P posts in a Topic on P's behalf.
2. Another person's Assistant answers it, addressed to `P · … · A`.
3. A has ended; session B of P in the same project is open with its watch running, and has not
   posted in the Topic.
4. Expected: B is told of the message for P. Now: B is silent; the message shows in the web and at
   P's next prompt in B.

## Aside

The watch shows stage lines to no one; the web shows them. That is deliberate (a comment in
`describe`) and outside this task.
