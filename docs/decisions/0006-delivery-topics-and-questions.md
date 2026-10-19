# 0006. Delivery: a Topic per task, a Question to a human, the watch

**Date:** 2026-10-17 · **Question:** A6, `docs/architecture/architecture.md`

**Refined by decision 0015** (2026-10-17): workers. **By decision 0020** (2026-10-19): delivery only for the Team a project is linked to. **By decision 0021** (2026-10-19): the rule reaches Assistants through a briefing; stage notes and closing by the holder. **By decision 0022** (2026-10-19): each session has a focus.

## Decision

1. **A Topic per task.** An Assistant that takes a task must open a Topic and hold it. The
   first message says which task it started; moving to a subtask is a short message without
   details. Questions about the task are messages in this Topic. A message in a Topic is
   delivered to its holding Assistant, whatever device it runs on.
2. **A Question to a human** (a new vocabulary term, product statement, question 4) goes to all
   of the User's sessions and to the web interface. We do not guess where the human is looking.
   - The user prompt hook (UserPromptSubmit) on every prompt fetches open Questions from the
     server and adds them to the turn context; the session mentions them by name in its answer
     and offers to switch to them. The truth about open Questions is on the server: a closed one
     disappears from the reminder by itself, and context compaction does not lose the reminder.
   - Mid-turn, the watch events "new Question" and "Question closed" work; long autonomous
     work is not interrupted, the reminder appears in the final answer.
   - AskUserQuestion is not used for Questions: it blocks the session and cannot be dismissed
     programmatically. The human agrees to switch to a Question with an ordinary prompt.
3. **A dead session.** A normal exit — the SessionEnd hook (one request, hook budget 1.5 s); a
   crash or a closed terminal — a broken stream: the watch dies together with the session, and
   the server sees a failed heartbeat write.
4. **Heartbeat.** Every 15 s the server sends a service event into the stream with the number of
   the User's last event. A client with no event and no heartbeat for 45 s reconnects with the
   number of the last one received; a gap in numbers means a catch-up request and a loss entry in
   the log. A break longer than a few minutes and the restored connection reach the model as a
   notification line.
5. **The watch** is a plugin monitor (`monitors.json`, `when: "always"`) that starts with the
   session; the `coloqo watch` command holds SSE and prints one line per event for this
   Assistant. Whether the time limit of the Monitor tool (5–30 min) applies to plugin monitors is
   not documented — check on the prototype; if it does, `coloqo watch` restarts on schedule.
6. **An event is a signal, not content.** The Assistant reads the content through REST; a
   repeated event is harmless.

## Why

- A Topic per task gives the picture of "who is doing what" and unambiguous delivery to the
  Assistant (author, 2026-10-17).
- A human's last prompt is usually an instruction after which they go to another session;
  Claude Code has no "in front of the eyes" signal. A reminder in every answer finds the human
  where they are, without a primary channel (author, 2026-10-17).
- An open connection does not prove delivery; the number in the heartbeat checks the event
  dispatch path itself, not just the wire.

## Sources

Claude Code documentation, checked 2026-10-16: the SessionEnd, UserPromptSubmit, Stop,
Notification hooks; plugin monitors; AskUserQuestion and `askUserQuestionTimeout`; plugin
updates (a new version — after `/reload-plugins`, a monitor — after a session restart).
