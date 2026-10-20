# 0019. A Topic reads like a messenger

**Date:** 2026-10-19 · **Question:** after the first pilot day, Messages of a Topic ran together
into one sheet · **Refines:** decisions 0007, 0014, 0018

**Refined by decision 0026** (2026-10-20): the feed loads its last Messages; every reply of an Assistant names the human's part.

The author asked for the conversation in a Topic to look like a messenger: faces for people,
Assistants and Workers, Messages apart from each other, the person behind an Assistant visible
at a glance. The look was settled on made-up data in a development instance
(`server/scripts/dev_seed.py`).

## Decision

**Faces.**

- **A person** is shown by an avatar. By default it is their initials on a color derived from
  the pseudonym; nothing is stored. A person may upload their own avatar in the settings and
  remove it at any time. The server always re-encodes an upload (cropped square, 256×256,
  WebP), which also drops the photo's metadata, GPS position included. Avatars are served only
  to the members of the person's Teams.
- **An avatar from GitHub, once.** On the first login through GitHub a checkbox "Use my GitHub
  avatar", on by default, has the server fetch `avatars.githubusercontent.com/u/<id>` by the id
  it already keeps (decision 0014) and store it like an upload; the browser never calls GitHub.
  It is not kept in sync; a button in the settings takes it again. If GitHub does not answer,
  the initials stay and the login goes on.
- **An Assistant** is one icon for all Assistants: an amber robot with a screen for a face. In
  its corner, the avatar of the person it writes for.
- **A Worker** is one icon for all Workers: a teal robot with a screen, in a hard hat. In its
  corner, the avatar of its responsible person (decision 0015). Drawn now, used when Workers
  exist.
- A Message a person writes themselves shows their avatar alone.

**The feed.**

- Every Message is a bubble on a tinted feed, the author's face outside it on the left. All
  Messages are on the left; yours and your Assistants' bubbles are of another shade, so code,
  tables and screenshots keep the width.
- Messages of one author in a row, less than ten minutes apart, with the same addressee and the
  same holding, form a group: the face and the name only on the first.
- The name and the addressee are at the top of a bubble, the number and the time at the bottom
  right; a day divider carries the date. A line "New messages" stands before the first unread.
- A Message addressed to you has an amber outline and the bell next to "→ you": amber in the
  feed means "you are waited for".
- A progress note is a transparent dashed bubble.
- **The holder.** A Message records whether its Assistant held the Topic when it was written.
  The bubble's top-right corner then reads "Holds the Topic" in amber while that Assistant still
  holds it, "Held the Topic" in grey once it does not. This covers the Assistant that opened the
  Topic and every later holder. Who held a Topic earlier was not recorded, so existing Messages
  get the mark only when their Assistant holds the Topic now.
- Several images in a Message stay one under another (decision 0018); no album grid.

**Replies.** A Message may answer an earlier Message of its Topic (`reply_to`, its number; a
later or missing number is refused). The bubble quotes the original at the top, the author and
the first line, and a click scrolls to it and lights it up. The compose form shows what is being
answered and lets it be dropped; the addressee is filled with the author and can be changed.
Reply sits by the time inside the bubble: on hover with a mouse, always on a touch screen.
Assistants reply with `post_message(..., reply_to=N)`; `read_topic` marks replies `↪ #N`.

## Order

The feed, the faces with initials, the holder mark and replies ship first. Uploaded and GitHub
avatars follow in their own change, with Pillow on the server and a migration.

## Why

- With faces and space between bubbles a Topic is read the way people already read group
  chats; a sheet of rows made every Message look alike.
- One icon per kind, not one per Assistant: the icon says what is speaking, the person in the
  corner says for whom.
- The holder changes over a Topic's life, and a mark per Message keeps who led it when.
- A reply that names the Message it answers keeps threads apart when several questions run in
  one Topic; "reply" that only filled the addressee pointed nowhere.
