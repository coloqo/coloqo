# Assistants ask the human less: lessons, mandate, count

## What happened

2026-10-21, the prototype team, a long task held in a Topic. The
assistant finished one subtask (publishing a section of docs), reported, and stopped with "next
waits: the canon for two more entities, then the backend". Nothing in that next step needed the
author: the screen had been approved, the canon change was already planned in the task's state
file. The author: "why did you ask me — you could have just continued".

The assistant wrote itself a note in its local memory: "the end of a subtask is not a stopping
point; if the next step is agreed and needs no human decision, do it". That note lives in one
project folder on one machine. The author's other projects, a teammate's assistant, even the same
author's session in another folder never see it.

The author wants Coloqo to be the engine that, in any project, cuts the number of times an agent
turns to a human and pushes assistants to act on their own. This file is the proposal for that.

## Facts checked (2026-10-21)

- **Assistant memory is per project and per machine.** Claude Code keeps it in
  `~/.claude/projects/<project>/memory/`; nothing of it reaches Coloqo or other members.
- **Team rules are decided, not built** (vision question 11, 2026-10-16). Stored in Coloqo with
  versions; reach the agent at session start through the plugin hook, connected by import in
  `CLAUDE.md`; changed by a Topic — anyone, an assistant included, proposes; only the owner of the
  Team or the Area approves; the Outcome is a new version.
- **The session start already carries behaviour.** The briefing gives Coloqo's own rules ("How to
  work in Coloqo"), the held Topics, the Inbox and the focus. It is the one text every assistant of
  the Team reads in every session.
- **A Topic knows its stages, not its plan.** `note_stage` records where the work is; nothing in
  the Topic says which next steps are already agreed with the human.
- **Coloqo does not know why an assistant stopped.** A turn that ends waiting for the human
  leaves no trace in Coloqo; the conversation frame (decision 0007) counts assistants' turns
  without a human only inside a Topic.
- **The prototype team has the rule, but blunt.** Its rules hub says "call the human when the
  decision is theirs, the action is hard to undo, or others will see it; otherwise act". The
  assistant still stopped: the rule did not say that a finished stage of an agreed task is not a
  reason to stop.

## Proposal

### 1. A lesson — a proposed Team rule born from a human's correction

When a human corrects how independently an assistant works — "you could have continued", "don't
ask me this, decide yourself", or the opposite, "this was mine to decide" — the assistant does not
only note it in its own memory. It proposes a lesson in Coloqo: a short record of the situation,
the expected behaviour, the reason, and the human's words verbatim.

- **It is a rule change of question 11, not a new concept.** A lesson is a proposal to the Team
  rules (or an Area's) with its trigger attached; the owner approves or rejects it; an approved
  lesson becomes a line in the next version of the rules, and every assistant of the Team gets it
  at its next session start — in every linked project.
- **Moderation is the point.** One remark of one person in one context must not become a rule for
  all by itself: the owner decides whether it generalises, and may rewrite it.
- **Coloqo's own rules tell the assistant to do this.** A line in "How to work in Coloqo": a
  human's correction of your independence is a lesson for the Team — propose it.

### 2. The Topic holds the mandate — the agreed next steps

The assistant stopped because the agreed next step lived in its local state file and it was not
sure the step was its to take. If a task Topic carries a short list of next steps agreed with the
human, the mandate becomes shared and visible.

- The assistant records agreed steps when the human agrees them (a stage note of a special kind,
  or a field of the Topic).
- On `note_stage`, Coloqo answers with the next agreed step: "next agreed: <step>; it needs no
  human decision — continue". The permission comes from the shared record, not from asking.
- A teammate's assistant reading the Topic sees the same plan, so a handover needs no question to
  the human either.

### 3. Count the turns to the human

An assistant that stops to wait for the human says so in the Topic with a reason from a short
list: a decision that is the human's, an irreversible action, a change to production, outward
communication, "just reporting". Coloqo counts per Team and per assistant the share of waits
without a decision behind them.

- The count feeds lesson 1: frequent empty stops of one kind are candidates for a lesson.
- It is also the measure the author asked for: whether Coloqo actually reduces turning to the
  human.
- What is visible to whom is a personal-data question (decision 0014): counts per Team are safe;
  per assistant — to its own human and the owner.

### Order

1 first: it works at once and for all projects, and question 11 already decided where it lives.
2 next: it pays most in long tasks, where most of the stops happen. 3 when there are lessons to
measure against.

## Boundary with a team's own rules hub

Lessons about working with people — when to call the human, when to continue, how to report — go
through Coloqo for any project. A team's domain rules (its canon, tracker, release) stay where the
team keeps them; for the prototype team that is its rules hub, until question 11 moves it into
Coloqo. Today's lesson is a refinement of the hub rule "call the human when the decision is
theirs", but its sense is general, so its place is Coloqo.

## Questions

1. **The trigger of a lesson.** Only an explicit correction by a human, or also the assistant's own
   judgement ("I stopped, the human said 'continue' without comment")? Explicit only is safer;
   the second catches more.
2. **Where an approved lesson goes.** Into the Team rules text itself, or into a separate
   "lessons" part of the briefing that the owner later folds into the rules? The second is lighter
   to approve; the first keeps one text.
3. **The mandate's form.** A kind of stage note, a field of the Topic, or a checklist in the first
   message that stages tick off.
4. **The reason list of item 3** and whether a wait without a reason is allowed at all.
5. **Before Team rules are built.** Lessons need question 11 built at least for the Team level;
   until then — a manual path: the owner adds an approved lesson to Coloqo's own briefing text?
