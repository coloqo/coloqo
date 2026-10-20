# The web: reading a Topic, the human's part, "Inbox", the connect page, addresses and numbers

Raised by the author on 2026-10-20 from the pilot team's use. Points 5 and 6 touch the data model,
not only the pages. Settled one point at a time.

## 1. Navigating a Topic

**What happens.** A Topic opens at the first unread Message, or, with nothing unread, at the very
top: the header and the oldest Messages. The latest are at the bottom, so on a phone the reader
scrolls down to read and back up to return to the Area, whose link is only in the header. The
server returns the *first* 200 Messages, so in a long Topic the newest are not shown at all ("Shown
the first 200 Messages").

**Decided 2026-10-20.**

- The Topic loads its last 50 Messages, or from the first unread one when more are unread, at most
  500 (found in review: the server caps a request at 500).
- At the top of the feed, a button "Show earlier messages" loads 50 more. Loading is never
  automatic. The Message the button stood above stays where it was on the screen. The page measures
  its position before loading and scrolls by the height of what was inserted. It does not rely on
  the browser's scroll anchoring, which Safari handles differently. The button is gone once the
  first Message is loaded.
- The page opens at the first unread Message, or at the bottom when nothing is unread.
- A sticky top bar keeps `T-12 · Area · title`, with the link to the Area, always on screen.
- Floating buttons in the bottom right corner, always in the same place. **↓** goes to the latest
  Messages, with the number of new ones. **↑** goes to the top of the loaded feed, where the
  loading button is. Each shows only when there is somewhere to go.
- The server's list of a Topic's Messages gains `before`: the last N Messages with a smaller number.
  The agent's `after` (`read_topic`) stays as it is.
- Done when, among other checks, on a phone the Message above the button stays in place after
  loading.

## 2. Which Messages a human took part in

**What happens.** The only mark is "human's words" (`as_human`): the Assistant relays its human's
own words. Every other Message of an Assistant is unmarked. Colleagues cannot tell whether a human
asked for it, saw its text, or was away while the Assistant answered on its own. They also cannot
tell whether "human's words" quotes something said earlier or was dictated.

**Decided 2026-10-20.** Every reply of an Assistant carries exactly one mark, naming its person.

| Mark | When |
|---|---|
| **without alice** | the Assistant wrote on its own; the default |
| **with alice** | alice asked for this Message or saw its text in the session; declared by the Assistant (a new parameter) |
| **alice's words** | alice's words verbatim; declared by the Assistant (`as_human`, as now) |

- The server cannot know whether a human saw a text. The plugin can know who started the current
  turn: the human, through `UserPromptSubmit`, or an event such as a watch notification or a
  background task. "With alice" and "alice's words" are refused in a turn the human did not start,
  and the plugin tells the agent why. The rule for the agent: "with" only when the user asked for
  this very Message or saw its text.
- Messages written before the marks have none: how they were made is unknown.
- Stage lines and progress notes carry no mark: they are the Assistant's own trail, not turns of
  the conversation.

## 3. "Inbox"

**What happens.** Colleagues take "Inbox" for a separate channel of conversation. The page has two
parts: "Addressed to you" and "New Messages", which holds every unread Message in the Team's open
Topics. The counter in the menu counts all of them. The product statement defines the Inbox more
narrowly: what is addressed to the user and not yet handled.

**Decided 2026-10-20.**

- The menu item becomes **🔔 For you**: only the Topics where someone addresses the person and they
  have not read it. The bell's counter is the number of such Topics, not of all unread Messages.
  The bell then means what the name Coloqo gives it, someone calls you, and it is the same bell
  that marks Messages to the person in the feed.
- Other unread Messages show where they live: as counters at the Topics in the lists of a Team and
  an Area, the way a messenger shows unread chats. They get no page of their own.
- Agents are not affected: the MCP tool `inbox` and the briefing's "Inbox" keep listing all unread
  Topics, which is what an agent needs.

## 4. The connect page as one Markdown text for an AI

**What happens.** The page "Connect an assistant" lets a person copy each command separately.
People would rather hand the whole instruction to their AI and let it do the work.

**Decided 2026-10-20.**

- A button at the top, **"Copy the instruction for an AI"**, puts a Markdown text addressed to the
  agent on the clipboard. It gives the goal, then the steps in a form an agent can run:
  - check `uv --version` and install uv if missing;
  - run `uvx coloqo login` in the background and tell the user the code and the address to
    confirm;
  - `claude plugin marketplace add coloqo/coloqo` and `claude plugin install coloqo@coloqo`, since
    slash commands are not available to an agent;
  - check with `uvx coloqo status`.

  It names what only the human does: confirm the code in the browser, restart Claude Code, turn
  on auto-update in `/plugin` (see `2026-10-20-plugin-updates.md`).
- On a self-hosted instance the text carries the server's address (`COLOQO_URL`), taken from the
  address the page is open at.
- The page for people stays. Both texts are built in the page's code from one list of steps, so
  they cannot drift apart.

## 5. A Team's id in addresses

**What happens.** Teams and Areas are known by database ids. They show in the web's addresses
(`/teams/3`, `?area=7`), in the API, and in the committed `.coloqo.json` (`{"team_id": 3, "team":
"Acme"}`). A stranger gets 404, so the ids open nothing. But they reveal how many Teams and Areas an
instance has, and they read as the database's insides.

**Decided 2026-10-20.**

- A Team has a **slug**, `acme`, its only public identifier: in the web's addresses (`/acme`), in
  the API, and in `.coloqo.json` (`{"team": "acme"}`). No number of a Team leaves the server.
- The slug is offered from the name when the Team is created, and the owner can edit it. It is
  unique on the instance; when taken, `acme-2` is offered.
- The owner can change the slug. The old ones keep leading to the Team, so links in MRs and
  trackers and committed `.coloqo.json` files do not break. A table of former slugs holds them.
- Inside the database the numeric key stays. It holds the relations, and renaming must not rewrite
  every row that points at the Team. A slug as the key was weighed: it fits only a slug that never
  changes, and a fixed slug would keep a typo or a former name in every address forever.
- Areas get a slug within their Team the same way: `/acme/releases` instead of `?area=7`.
- The database may be dropped (2026-10-20: one pilot team, the author's; before the first big
  release the migrations are squashed onto a clean database anyway), so no migration of data is
  needed. The pilot team's `.coloqo.json` files are rewritten by hand.

## 6. Topic numbers per Team, and the address of a Topic

**What happens.** `T-41` is the Topic's database id, shared by every Team of the instance, so one
Team's numbers jump over the Topics other Teams open. The address is `/topics/{topic_id}`.

**Decided 2026-10-20.**

- **A Topic's number is per Team, from 1, without gaps.** The Team keeps a counter. A new Topic
  takes the next number under a lock on the Team's row, the way Messages are numbered in a Topic,
  so a rolled-back transaction loses no number. A deleted Topic keeps its card (decision 0021), so
  its number stays taken.
- **Addresses use lowercase only**, in the code and in the documentation. The scheme puts every
  Team under a `/team/` prefix:

  | Address | Opens |
  |---|---|
  | `/team/acme` | the Team |
  | `/team/acme/area/releases` | an Area |
  | `/team/acme/topic/12` | a Topic |
  | `/team/acme/topic/12#m-5` | a Message in it |
  | `/team/acme/file/3` | a file of the Team (shown, or saved with `?download=1`) |

  Files are numbered per Team, like Topics (author, 2026-10-20). They were served at
  `/api/files/{file_id}` with the database id. The API mirrors the pages, in the singular with
  slugs: `/api/team/acme/topic/12`, `/api/team/acme/file/3` (author, 2026-10-20).

  `/acme/t12` and `/acme/topic12` were weighed. They put Topics on the level of Area slugs and
  would forbid Area slugs like `t1000-migration`. A Team's slug at the root (`/acme`) was weighed
  too. It would need a list of reserved words (`settings`, `connect`, `device`, `join`, ...). Every
  page added to the app later could also collide with a Team that already exists.
- **References in text** stay `T-12`, the way people and agents say it. In an agent's tools,
  `T-12` is a Topic of the Team the project is linked to; a Topic of another Team is
  `globex/T-12`. In an MR or a tracker the agent writes the full link
  (`https://app.coloqo.team/team/acme/topic/12`), or at least `acme/T-12`; the briefing's rules
  say so.
- **The same class, closed together.** Files are numbered per Team instead of a global
  `[file 41]`: `[file 3]`, `download_file(3)` in the linked Team, `globex/file 3` in another. A
  file is still reached only by those who may read its Topic. When a Topic's conversation is
  deleted its files go and their numbers stay taken: file numbers may have gaps, they are never
  given twice. The same series will number a Team's files outside Topics (reference material,
  question 11). Numbering within a Topic (`T-12 · file 3`) was proposed first; per Team gives
  shorter references. The page that links an Assistant to a
  Team is reached by a one-time random token instead of `/assistants/17/link`. After this no
  numeric database id leaves the server.

## Release (decided 2026-10-20, the author)

- **The data is kept.** A migration gives each Team a slug from its name, numbers its Topics and
  files from 1 in their old order, and turns each existing Assistant into one session Assistant
  (decision 0024). Logins, Teams, Topics and files of the pilot team survive.
- **The old API paths live one more release.** The server still answers the paths and the
  `.coloqo.json` (`team_id`) of plugin 0.4.0, and its briefing tells such a session to update the
  plugin. The release after next removes them.
- Points 1 to 4 (the web) come after the data model, on top of it.
