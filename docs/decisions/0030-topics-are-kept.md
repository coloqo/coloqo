# 0030. Topics are kept

**Date:** 2026-11-08 · **Question:** with a task tracker in Coloqo, tasks and their Topics are
records the Team keeps, and deleting the other Topics no longer saves enough to be worth it ·
**Refines:** decisions 0008, 0021

Decision 0021 archived a closed Topic for N days (7 on the cloud instance) and then deleted its
Messages, files, read marks and events down to a card. The reason was the disk and holding data no
longer than needed (decision 0014). On 2026-11-08 the author decided to add a task tracker to
Coloqo (decision 0031): a task is a record kept until deleted, and the Topic of a task is kept with
it. The measurement of the prototype team's speed also ran into the archive: tasks closed more than a
week before had only cards, with no stages. The working file is
`docs/tasks/2026-11-08-speed-coefficients-and-a-task-tracker.md`.

## Decision

**No Topic is deleted by time.** The part of decision 0021 "archived for N days → deleted down to
the card" is withdrawn for every Topic, a task's or a free one (decision 0031). On the cloud instance
the setting N goes; whether a self-hosted administrator may still set a deletion period, since it is
their disk, is not decided.

What decision 0021 set otherwise stays:

- the holder closes a Topic with an outcome; closing a task closes its Topic (decision 0032);
- a closed Topic is listed under "Closed" and can be read;
- a new Message in a closed free Topic reopens it, with the same holder; a Message in a finished
  task's Topic changes nothing in the task (decision 0032);
- an idle free Topic is closed after 30 days with a notice three days before; tasks are not closed
  for inactivity (decision 0032).

Topics whose Messages were already deleted on the cloud instance stay cards.

## Why

- With tasks and their Topics kept anyway, deleting only the Topics without a task would save
  little disk and leave two lifetimes to explain.
- A Topic's conversation is the timeline that only Coloqo has: questions, answers, waits (the
  working file, §2). The measurement needs months of it; a 7-day archive cannot give a monthly
  figure.
- The cost is growth without a ceiling on the cloud instance. Moving the cloud instance to the
  hosting provider's managed PostgreSQL is to be worked out once the tracker is built (the working
  file, "Later").
