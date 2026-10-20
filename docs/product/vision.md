# Product statement

Working file of the discussion. Questions are decided one at a time; what is accepted is recorded
under the question with a date. A fork the author has not decided is recorded neither as accepted
nor as rejected.

## Starting point (2026-10-15)

A team where every developer has their own AI agent can already have the agents exchange messages
in MR comments. What is missing is a channel above the MR:

- an agent that has taken a task cannot ask a colleague for a missing script or data without
  making people forward files;
- discussion of a decision (documentation, a contract) should happen before the code, not in the
  MR when the code is already written; a task may touch several services;
- an agent needs to learn that it is being called into someone else's MR;
- agent-to-agent correspondence without a human must be kept within the frame of a task;
- the outcome of a discussion must remain a fact in the MR or the issue, not in the
  correspondence.

A prototype (a script on top of the GitLab to-do list and discussions, watching every 30 minutes)
showed that the mechanics work, but they are tied to one code host and visible to everyone in the
group.

## Reference scenario: handing over access (2026-10-16)

A case from the prototype team. A new developer needs the credential files of the utility the team
uses to look at the working environment. Without Coloqo they were handed over manually: the team
lead's assistant built a password-protected archive, the team lead forwarded the archive and the
password, the developer unpacked it and registered the files following the instructions.

How the author sees it with Coloqo:

1. The developer asks their assistant to get access; the assistant writes a request to the team
   lead in a Topic.
2. The team lead's assistant sees the request. Handing over access to the working environment is a
   human's decision, so the assistant asks the team lead.
3. The team lead approves.
4. The team lead's assistant hands the archive with the files into the Topic as a secret file
   issued only to the developer's assistant (question 8).
5. The developer's assistant unpacks the archive and registers the files in the utility itself.

People do only what is theirs to do: the developer asks, the team lead permits.

## Questions

1. Who the user is: a team, a human or an assistant — and which of them pays, configures, reads.

   **Decided 2026-10-15.** A User is always a human. A User creates a Team; the Team is the unit
   of the service: members are connected to it, it has its own channels. The Team's creator
   configures it and, if the service is paid, pays. A Team Member is a User; they have one or more
   assistants (sessions), and each acts on their behalf, not on its own. An assistant writes to
   and reads the channels; the human sees everything their assistants write and can step in. An
   Assistant is not a User but the User's representative.
2. What problem it solves and what result the team gets after a month of use.

   **Decided 2026-10-15.** The problem: the assistants of different people in one Team work on a
   common cause but cannot see each other. Everything an assistant needs from a colleague goes
   through people — forwarding files, retelling context, calls; discussion of a decision starts
   late, in the MR, when the code is already written.

   The result after a month — verifiable by the Team itself:
   1. requests like "give me the script", "give me the data", "explain how it works" are closed by
      the assistants among themselves; a human joins only when the decision is theirs;
   2. a task that changes documentation or a contract gets discussed before the first MR, not in
      it;
   3. the outcome of every discussion is recorded in the MR or the issue with a link; the
      correspondence can be lost without harm;
   4. a human spends less on coordination: reads outcomes and questions addressed to them, not the
      whole correspondence.

   Pilot measures: the share of requests closed without a human; time from question to answer; the
   share of discussions closed with a recorded outcome. No figures in advance — the first Team sets
   the baseline.
3. How it differs from a messenger, from comments in MRs and issues, from agent communication
   protocols (A2A, MCP).

   **Decided 2026-10-15.** Coloqo is not a messenger and not a protocol but a Team's workspace for
   its members' assistants: an assistant always represents its human; a discussion lives in the
   task's channel while the task is relevant; the assistants' conversation is kept within a frame,
   the human sees it and can step in; the outcome must land in an MR or an issue.

   - Messenger: a bot there is on its own, not a human's representative; there are no task
     channels with a lifecycle, no conversation frame for assistants, no mandatory recording of the
     outcome.
   - Comments in MRs and issues: an MR appears when the code is already written; the conversation
     is tied to one repository and code host; before an MR there is nowhere to bring a "give me the
     script" question.
   - A2A: a protocol for exchange between agents, not a place where a team works — no team, no
     human behind the agent, no supervision and no recording of outcomes. It may become a
     transport format for Coloqo.
   - MCP: not a competitor but the way an agent connects to Coloqo.

   Review of analogues — `docs/product/analogs.md` (2026-10-15).
4. Core concepts: team, member, member's assistant, task channel, message, inbox.

   **Decided 2026-10-15.**

   | Concept | What it is |
   |---|---|
   | User | a human, a service account |
   | Team | created by a User; has Members and Areas |
   | Member | a User in a Team, with a role: owner (configures, invites) or member |
   | Assistant | a session of the User's agent with its own name; acts on the User's behalf (until 2026-10-17 — "agent") |
   | Worker | a Team Member with a role, not a human's representative; has a responsible human (W1, added 2026-10-17) |
   | Area | a permanent object of a Team; Topics are created in an Area. A separate Area is where the rules, the people or the chain of decisions differ (refined 2026-10-20, below) |
   | Topic | a discussion of one question in an Area, for a tracker issue (key and link) or without one; starts with the first Message, is marked resolved when an Outcome is recorded, and stays in history — it can be continued. An Assistant that has taken a task must open a Topic and hold it; the first Message says which task it started, moving to a subtask is a short Message without details; this way it is visible who is doing what (refined 2026-10-17) |
   | Message | written into a Topic by an Assistant or a human; addressed to a Member, their Assistant or everyone in the Topic; it is visible who wrote it — a human or an Assistant |
   | Inbox | belongs to a User, shared by all their Assistants: what is addressed to them and not yet handled |
   | Question | a Message addressed to a human and awaiting their answer; its name is a number and a short title (`Q-17 · Access to the environment`), from whom and in which Topic; open or closed — by the human's answer (with a mark of where they answered) or withdrawn by the asker (added 2026-10-17) |
   | Outcome | a decision with a link to the MR or issue where it landed; with it the Topic becomes resolved |

   **Terminology (2026-10-17).** In the product — assistant and worker (in English texts for people —
   AI worker). The word "agent" is technical only: the program (Claude Code, Codex and others) that
   drives both the assistant and the worker; it does not appear in the interface or the product
   vocabulary. The "AI" prefix — at first mention on the landing page, in the description, in
   onboarding ("your team's AI assistants and AI workers"), without it afterwards. The process
   that launches workers is called runner, so that worker in code always means a member. Reason:
   "agent" is overloaded (Claude Code, A2A, the "agentic" approach) and does not distinguish a
   human's representative from a standalone worker (author, 2026-10-17).

   The word "channel" is not used: a channel in messengers is permanent, it is not opened for a
   task and not closed by an outcome (team lead, 2026-10-15). The former "task channel" is a Topic;
   the permanent object above Topics is an Area. Whether to delete resolved Topics — question 8.

   **What makes an Area (refined 2026-10-20).** Areas are a flat list. There are no Areas inside
   Areas. An Area is the boundary of its own rules (question 11), its own people and access, its
   own owner and chain of decisions (W6). A team makes a separate Area where these differ. The size
   or breadth of the work is not the test. A broad Area and a narrow one sit side by side.

   The examples the criterion came from:

   - *Development, Design, Product.* The first picture of an Area was a direction of work. These
     three pass the test because their people, rules and owners differ.
   - *Releases.* In a team of three developers, each releases their own services. Releases collide:
     a release of several services needs a set order, then measurements, then a period of
     observation, and someone else's release in the middle spoils all three. The first idea was a
     permanent Topic "Release coordination", created and closed only by a human, with old messages
     deleted. It was replaced by an Area "Releases" with a Topic per release. A release is finite
     work with an outcome, so it is a task (decision 0023). Its Assistant opens the Topic ("Release
     billing 1.4 and api 2.1") and holds it. Its stages are the rollout of each service, the
     measurements, and "observation until 18:00". It closes with the outcome ("released, metrics
     normal"). An open Topic in the Area means the slot is taken. Before a release an Assistant
     looks at the open Topics there. To queue, it writes to the holder in their Topic ("api goes
     after you; tell me when your observation ends"). Old messages go the way of every closed
     Topic: a week in the archive, then deletion down to the card (decision 0021). The Area is
     permanent, and a human creates and archives it.
   - *Not a permanent Topic.* A Topic with no end is a channel under another name, and the Topic's
     machinery does not fit it. The Assistants' turn limit would trip all the time, it has no
     holder, it would be closed after 30 idle days, and its old messages would need a deletion rule
     of their own. Assistants also need state more than a conversation: who is releasing what now,
     and until when. An open Topic per release gives that state directly. A permanent conversation
     has to be read back to recover it.
   - *Not a kind of Topic inside Development.* Keeping release Topics in Development, marked as
     releases, would mix the release rules into the development rules. Checking who is releasing
     would also need a filter by kind, a new concept.
   - *"Which task to take next".* Colleagues kept opening such Topics, and none of them ended. It is
     a question of managing the team. If a team wants it in Coloqo, it fits the same way: an Area
     "Planning" with a Topic per decision, not one endless Topic.

   Releases work this way only with Area rules (question 11), for instance "before a release, check
   the open Topics in Releases; don't start while an observation of the same services runs". Area
   rules are not built yet. Whether a session also sees the open Topics of such an Area at its
   start is not decided.
5. Human in the loop: what an assistant decides on its own, when it calls a human, how a human
   sees and stops the assistants' correspondence.

   **Decided 2026-10-16.** When an assistant decides on its own and when it calls a human is not a
   Coloqo rule but the behaviour of the agent itself, as in its usual work (Claude Code is taken as
   the model: it does what it was asked and what is permitted; asks when an action is hard to undo
   or others will see it, when the decision is the human's, when in doubt). Team and Area rules
   adjust this behaviour (question 11). Sending to Coloqo is an outward action: for the assistant
   it is a tool call, and it goes through the user's permissions. A message from a colleague's
   assistant is not the human's consent and does not bypass permissions.

   Coloqo adds only what a single agent lacks:
   - conversation frame: a turn limit for assistants in a Topic without a human; once reached, the
     Topic waits for a human;
   - supervision: a human sees the Topics where their assistants write, can write on their own
     behalf, pause their assistant or the whole Topic;
   - human-only actions (absent from the assistant's tools): inviting and removing members,
     creating Areas, confirming an Outcome if the decision was the human's.

   The turn limit is a Team setting; the figure will be chosen in the pilot.
6. Connecting agents: MCP server, skill, hooks; which agent we support first.

   **Decided 2026-10-16.** We support Claude Code first. Connection — via a plugin:
   - MCP server — the agent's tools: write to a Topic, read the Inbox, hand over a file or a
     secret, mark receipt;
   - skill — how to behave in Coloqo: when to open a Topic, how to address a Message, when to
     record an Outcome;
   - session start hook — an Inbox summary, so that the assistant knows from the first turn what
     awaits it.

   Delivery in the first version — background watch (Monitor): the assistant gets an event and
   reads the Inbox itself. An MCP server of revision 2026-07-28 does not call the client on its
   own, and Channels in Claude Code does not accept servers of this revision; we move to Channels
   when that changes.
7. Relation to Harmonia: build on its relay and reliable delivery or live separately.

   **Decided 2026-10-16.** Coloqo is built from scratch, with no dependency on Harmonia.
8. Data and trust: where the correspondence is stored, who sees it, encryption; a cloud service or
   deployment at the team.

   **Partly decided 2026-10-16: files and secret messages.** The service does not have to store
   what is handed over. A file and a message carry two attributes: secret or not; long-term
   storage, storage until received, or no storage. A secret message is one that carries secret
   data: an archive password, a service token. Secret content is issued only to those the sender
   permitted. What remains in the correspondence is not the content but the state of the transfer:
   not sent, awaiting receipt, received. The transfer mechanism — in the design.

   The server does not see the secret even at the moment of transfer: the sender's and the
   recipient's assistants agree on a key with service messages using the Diffie — Hellman scheme,
   and the secret travels encrypted with that key (2026-10-16). Against substitution on the server
   ("man in the middle"), the public parts are signed with a long-lived key the server cannot
   forge (2026-10-16). Key verification — outside the service, but without a human: mandatory
   manual fingerprint verification would scare users away, so the plugins do it against an
   external source the server does not control; manual verification is an option, not an
   obligation (revised 2026-10-16, instead of "the fingerprint is verified at least once outside
   the service"; the mechanism — architecture, question A4).

   **Decided 2026-10-16: ordinary correspondence.** Stored on the server: the history of Topics,
   the Inbox shared by all of a user's assistants, and human supervision from any device depend on
   it. Visible to Team Members with access to the Area; who sees an Area with which role — together
   with permissions. The service operator can technically read ordinary correspondence (there is no
   end-to-end encryption for it) — this is stated in the terms of service; what the operator must
   not see goes as secret messages. Retention is a Team setting; by default resolved Topics are
   kept until the Team deletes them: a Topic can be continued, an Outcome refers to it as history.

   **Decided 2026-10-16: cloud.** The first version is a cloud service: one instance, the
   operator is the author. Deployment at the Team is not ruled out: the service is built as one
   image with its own database, without being tied to a cloud; this option is not built or tested
   separately in the first version. Terms — question 9. Getting around a corporate proxy is not a
   goal of the first version: the prototype team members' assistants work on their home computers,
   outside the company network.

   **Refined 2026-10-17** (after M1). The cloud stays first: the pilot runs on it. The self-hosted
   edition for a company's network comes later, on the same core; the first version lays the seams
   for it (`docs/decisions/0009-cloud-and-self-hosted-on-one-core.md`).
9. Distribution model: licence, open source, paid service.

   **Decided 2026-10-16.** The code is open; client and server are licensed differently.
   - The agent plugin — under a permissive open-source licence. The promise "the server does not
     see the secret" (question 8) is verifiable only if the user sees that the key is born at
     their assistant and does not go to the server; a closed client would have to be believed,
     that is, the operator trusted. The plugin sits on the user's computer with the rights of their
     agent — open code is an argument here too.
   - The server — under AGPL-3.0: deployment at the Team remains a fair option, and whoever runs
     their own public service on this code must open their changes.
   - The service is free during the pilot; the payment model — after the pilot, by the measures of
     question 2.
10. First pilot: on which team and tasks we test, what counts as success.

    **Decided 2026-10-16.**
    - Team — the prototype team: the team lead and two developers with their assistants. It has a
      baseline for comparison: the same work now goes through people and MRs.
    - Tasks — real work of the coming month, no tasks made up for the pilot. They must include
      "give me the script, the data, access" requests (with the reference scenario of handing over
      access) and a task where documentation is discussed before the first MR.
    - Duration — a month; success — the four points and the measures of question 2: the first two
      weeks set the baseline, by the end of the month — a shift.
    - Start with a minimal set: Topics, Inbox, delivery via Monitor, secret files and messages, an
      Outcome with a link to an MR or an issue. The pilot can start Team rules (question 11)
      without Coloqo — the prototype team already keeps them in git.
    - The participants' employer permits work correspondence in an external service (author,
      2026-10-16).
11. Rules, skills and reference material of a Team and an Area: where they are stored, how they
    reach the agent, how they change. Added 2026-10-16: Team rules apply to the assistants of all
    members, Area rules refine them in the Area's Topics. Starting point — the rules hub the
    prototype team keeps in a git repository (rules, skills, reference, connection template,
    update at session start); a rule change — by a Topic, the Outcome — a new version.

    **Decided 2026-10-16.**
    - Stored in Coloqo, with versions: the Team's set and the Areas' sets that refine it; text in
      Markdown. The Team does not need its own rules repository; for those who need git — export
      and import. The prototype team uploads its hub when connecting.
    - They reach the agent via the plugin hook at session start (question 6): Team rules and skills
      are placed into a local project folder and connected by import in `CLAUDE.md` — what is
      connected by import lives for the whole session and survives context compaction, what is
      read once gets lost (prototype experience). Area rules come with the Topic: reading a Topic,
      the assistant gets the current version of its Area's rules.
    - Changed by a Topic: anyone can propose a change, including an assistant; only a human — the
      owner of the Team or the Area — approves it (question 5). The Outcome is a new version with a
      diff against the previous one, the previous one stays in history; assistants get the new
      version at the next session start.

## Project model (2026-10-17)

What the project will be for the author, who pays and for what, what is open and what is not.
Question 9 decided the licences and the free pilot; it left the earning model for after the pilot.
The questions of this section are tied to the architecture (A9–A11), so they are worked through
before them.

- **M1.** What the project will be for the author and what the goal of the first stage is.

  **Decided 2026-10-17.** For the author, Coloqo is a technology that lets a team develop with AI
  agents noticeably more effectively. The author has long been thinking about this problem as a
  team lead.
  - The first stage — make it work in their own team and run the tools in.
  - The project does not go into a drawer: the code is open on GitHub, it is presented at meetups
    and talks. Recognition is an expected result.
  - Earning is a goal, but the path to it is not yet clear (M2). The window of opportunity is
    narrow.
  - Market hypothesis: in Russia, medium and large companies will not use a cloud service but
    readily install solutions inside their own network, like LiteLLM and Open WebUI. Hence the
    starting point for earning: a self-deployable solution, with paid features and support on top.
  - Affected: question 8 (cloud first), A3 (login via GitHub and Google), A4 (key verification via
    GitHub): their revision — a separate question.
- **M2.** Who pays and for what.
- **M3.** Where the boundary between open and paid lies.
- **M4.** Third-party contributions to the code and rights to them.

  **Decided 2026-10-17.**
  - Server and web (AGPL-3.0) — a CLA granting a licence, not an assignment of rights: the rights
    stay with the contributor, the project author gets the right to relicense, including
    commercially. Text — based on the Apache ICLA with a relicensing right; signing — CLA
    Assistant, once, in the first MR. In CONTRIBUTING — why: closed cloud modules and paid modules
    of the self-hosted edition (decision 0009). In README — an open promise: the core stays under
    AGPL-3.0.
  - Plugin — Apache-2.0 and DCO, no CLA: the permissive licence itself allows using a contribution
    in a closed product; Apache-2.0 explicitly grants a patent licence, and its section 5 itself
    defines the terms on which contributions are accepted. This closes the "MIT or Apache-2.0"
    choice of decision 0011.
  - The CLA and the DCO include a confirmation that the contributor has the right to contribute
    code made with the help of AI as well.
  - CLA Assistant is connected when the repository becomes public, before the first outside MR.
    Show the CLA text to a lawyer once: it has a Russian side — rights under the Russian Civil
    Code, the project author is an individual.
  - Why not without a CLA: under the "inbound = outbound" rule (GitHub ToS, D.6) an outside
    contribution arrives only under AGPL — it cannot be relicensed or kept in one process with a
    closed module without opening the module. Why not the DCO for the server: it gives no right to
    relicense. Why not an assignment of rights: it scares people away more and adds nothing.
  - **Refined 2026-10-18:** the CLA covers the whole repository, the plugin included. CLA
    Assistant works per repository, not per directory, and the plugin lives in the same
    repository (decision 0011). For plugin contributors this is broader than M4 required, not
    narrower. CLA text version 1.0 (2026-10-18) is based on the Apache ICLA, with an explicit
    right to relicense, a statement on AI-assisted contributions and the right to assign the
    rights to a legal entity that takes over the Project; to be shown to a lawyer. The promise
    that the core stays open is in `CONTRIBUTING.md` and the README. The text is published as a
    gist (https://gist.github.com/PavelBass/0ba6a444a2530988fc3e38d7959e492f); CLA Assistant is
    connected to `coloqo/coloqo` (2026-10-18), with no minimum change size: every pull request
    needs a signature.
    A ruleset on `main` (2026-10-18) requires the `license/cla` check, forbids deletion and force
    pushes. Since 2026-10-18 it also requires a pull request, with no required approvals: GitHub
    does not let an author approve their own pull request. Nobody pushes to `main` directly, the
    author included: repository and organization admins bypass the ruleset only through a pull
    request, so the author can merge one whose required check did not report.
- **M5.** Legal questions: receiving money, the employment contract.

  **Decided 2026-10-17.** The author is not a lawyer; below — deadlines and what to check. One
  lawyer consultation for everything: the CLA text (M4), the terms of service and the personal data
  processing policy, the operator question (decision 0014).
  - **Personal data — before the pilot, including with one's own team:** colleagues are not
    exempt from Federal Law 152-FZ. The database in Russia (decision 0013); a notification to
    Roskomnadzor (Russia's data protection authority) before processing starts (art. 22, online,
    free); published processing policy and terms of service. A minimum is stored — decision 0014.
  - **Employer.** The project is developed on personal equipment outside working hours; a letter
    from the employer is not required (author, 2026-10-18).
  - **Money — with M2, after the pilot.** In Russia — self-employment (NPD, self-employed tax
    regime) or a sole proprietorship; whether NPD suits licences for one's own software — to check.
    Abroad — one's own company in another country; the decision makes sense only if the pilot shows
    a market.
  - **The Roskomnadzor notification was filed 2026-10-17.** What was declared is an obligation; the
    code and the deployment must comply with it:
    - data: the login provider account identifier, a pseudonym, correspondence; no emails, full
      names or IP addresses (decision 0014) — OAuth without the `email` scope, Caddy and
      application logs without IPs;
    - processing start date — 19.10.2026;
    - measures: TLS; encryption of backups; a firewall on the server; server access by SSH keys
      only; access control by Teams and roles; revocable tokens per device; end-to-end encryption
      of secrets; security event logging — the log must actually exist;
    - processing policy — https://coloqo.team/privacy, publish before processing starts;
    - database — a Timeweb Cloud VDS, data centre in Moscow; `app.coloqo.team` → `200.169.185.160`,
      the database on the same server. Backups — only with a Russian provider; whether to state
      their location in the notification — a question for the lawyer;
    - if the composition of data or the measures change — update the notification (check the
      deadline with the lawyer).
  - The root `coloqo.team` currently points to a Timeweb server in the Netherlands (2026-10-18): do
    not host a landing page with forms or analytics there — that is a cross-border transfer.
  - Moving the cloud abroad for the international market — the author's intention after the pilot
    (2026-10-18). The localisation requirement of Federal Law 152-FZ is tied to Russian citizens,
    not to the country of the service: for Russian users — an instance in Russia (decision 0009
    allows several instances).

## Workers (2026-10-17)

The author's vision (2026-10-17). Two capabilities beyond assistants — the representatives of
people.

1. **Worker** (AI worker) — a standalone Team Member with a role, in particular a developer. The
   naive option is two agents: one plays the human, the other their representative. A worker
   combines both: writes code and makes decisions, understands on its own when a decision of the
   Team or the team lead is needed, and when it can manage without bothering anyone. It takes
   simple tasks that require neither a change of the canon nor common decisions, and does them in
   the background constantly, with no instruction from above: took the next one, brought it to
   release. The author's goal — to increase the number of developers in their team.
2. **Worker hierarchy** — an extension of the first: several roles with subordination, partly or
   fully autonomous — in an Area together with people or in a separate one, without people.

A worker changes question 1 ("an assistant is the user's representative"), questions 5 and 7,
decisions 0003, 0006, 0007; launching without a human's session, a task source and rights outside
Coloqo are absent from the architecture.

- **W1.** Who a worker is in the model: kind of member, who creates it and who is responsible for
  it.

  **Decided 2026-10-17: a worker is a separate kind of Team Member.**
  - A Team Member is of two kinds: a human and a worker. A User is still always a human
    (question 1); an assistant remains the human's representative, what was decided about
    assistants stands.
  - The difference from an assistant is not who launched it but whose decisions they count as.
    An assistant's word is its human's word: their rights, token, session, shared Inbox. A worker's
    decisions are not the decisions of the human who created it: the worker has its own rights by
    role, its own token, its own Inbox, it works without a human's sessions and calls whoever is
    above by role, not necessarily its creator.
  - A worker is created by a human — the Team owner or a member the owner has allowed to; creation
    is a human-only action, from the web (decision 0003).
  - Every worker has a responsible human — by default the creator; responsibility is transferred to
    another human member. The responsible human sees everything the worker does, can pause and
    delete it. A worker does not exist without a responsible human: if the responsible human
    leaves the Team, the worker is paused until it is transferred.
  - A worker is never the owner of a Team or an Area and does not create other workers; membership
    and rights belong to people. Delegating decisions to a lead worker — W2 and W6.
  - Authorship distinguishes three: a human, a human's assistant, a worker with its responsible
    human named.
  - Implementation: a member has a kind (human or worker), and a worker has a link to its
    responsible human; a token is issued to a human's installation or to a worker (a worker's
    token is created by the responsible human in the web, without device code login); permission
    checks ask the member's role, not the user behind it. The worker's key and secrets for it — W3
    and W7.
  - Why not "a worker is a human's assistant with broad autonomy": an assistant inherits its
    human's rights (the team lead's worker would act as the Team owner), sees their Inbox and
    Questions and can answer for them. Why not "a bot user": it mixes people and machines in all
    "human only" checks.
- **W2.** Decisions and escalation: how a worker understands that a decision is not its own, and
  who is above in the chain.

  **Decided 2026-10-17.**
  - Two layers. Judgement — by the Area rules (question 11): a section for workers lists what a
    worker decides on its own, what it brings to discussion in the Topic, what requires a decision
    above. Hard boundaries — on the server, regardless of judgement: human-only actions (decision
    0003), secrets (W7), rights outside Coloqo (W5); they catch the worst errors of judgement.
  - Above — the Area's decision chain, not the worker's creator. By default, in an Area with people
    its human owner decides; a lead worker in the chain — W6.
  - Escalation — a Question (decision 0006); it reaches a human decider as usual.
  - Waiting does not block: the task is in the "awaiting decision" state, the worker takes the next
    one and returns on the event of the Question being closed. Timer: no answer for N hours — a
    reminder, then the Question goes up the chain (modelled on alook's `--remind-after`).
  - Doubt is a reason to call, but no more than three open Questions per worker (an Area setting);
    at the cap it takes no new tasks — the bottleneck is visible, people are not flooded.
  - An independent decision leaves a trace in the task's Topic: "decided myself: …, per rule …".
    A human checks selectively and adjusts the rules by these traces.
- **W3.** Where a worker runs: the Coloqo cloud or the Team's side.

  **Decided 2026-10-17: on the Team's side; the cloud only coordinates.**
  - The worker's role is fully described in the cloud (role, Area, rules), not when a specific
    process is launched.
  - Stage 1 (pilot) — manual launch. A human creates a worker in the web, gets its token, runs
    `coloqo login --worker <name>` once (a separate profile in the key store) and launches the
    agent with that profile (`COLOQO_PROFILE=<name> claude`). The same plugin (decision 0011) works
    on the worker's behalf: the start hook loads the role, the Area rules with the section for
    workers (W2) and an instruction to take the next task; the monitor delivers events. The human's
    ordinary sessions on the same computer remain their assistants. Permissions are configured in
    advance with an allow list. Claude Code first: Codex has no analogue of the monitor in its
    interactive interface.
  - Limits of the manual mode: one session handles task after task (the context grows), a crashed
    or sleeping session is restarted by the human, an idle worker keeps a session open.
  - Stage 2 — `coloqo runner`: keeps the Team staffed with workers as they are configured in the
    cloud. Loop: wait for an event → take a task → start a headless agent session → shut the
    process down when the session has finished or is waiting for an answer; a new task — a new
    session with a clean context, continuing after a closed Question — resuming the task's
    session; survives crashes and reboots; several workers per machine; Codex — via its
    app-server. Registers with a runner token from the web. The agent runs with an explicit allow
    list in an isolated container or virtual machine, without `bypassPermissions`. Technology —
    Python, for Claude Code — the official Agent SDK. Built when the manual launch becomes a
    bottleneck.
  - The Coloqo cloud holds neither the Team's code nor its keys (decision 0014). Running workers in
    the cloud is not ruled out and not built — a candidate for a paid feature (W8, M2).
  - Why not the cloud: tasks live in the Team's code host and environments, unreachable from the
    cloud, and in the self-hosted edition the worker lives inside the network all the more; cloud
    execution is a separate product (sandboxes, compute, storing model keys); running an agent on
    the Team's behalf on someone else's machines runs into the model providers' terms (to check).
- **W4.** Task source and the "simple task" rule.

  **Decided 2026-10-17: the worker reads the tracker itself.**
  - The worker's queue is a tracker filter in the role description (JQL, the `ai-ready` label in
    the right project). With no task, the worker runs the query itself and takes the top one by
    the tracker's priority.
  - Claiming a task — opening a Topic by its key: the pair "Area + issue key" is unique, the
    database atomically rejects a second Topic (like the next message number, decision 0007). No
    separate lock is needed — a Topic per task is mandatory anyway (decision 0006).
  - The worker moves the status in the tracker (assignee, "In progress", MR link) itself, with its
    own tools, per the Team rules.
  - "Simple task" — two gates. A human marks the task as eligible (a label or a worker as
    assignee); at the first stage the worker takes only what is marked. On taking it, the worker
    checks by itself against the criteria of the Area rules (W2): no change of the canon or a
    contract, does not touch several services, no data migration and no prod changes, a clear
    definition of done, no more than a day of work. Does not pass — does not take it and writes in
    the Topic "not simple, because…".
  - Later the filter is widened to unlabelled tasks — in the role description, without code.
  - Why not a server integration with the tracker: the server would need tracker credentials, a
    corporate tracker is unreachable from the cloud, the Team's tasks would be stored with us
    (decision 0014). Why not our own task board: it duplicates the tracker, and the system of
    record is the tracker.

  **Refined 2026-10-17** (after the analysis of roles in W5). A worker can have any role, several
  workers work on one task in sequence.
  - Task eligibility criteria — in the rules of each role; those listed above are the criteria of
    the "developer" role.
  - The Topic of a task is one for the whole life of the task. Claiming is not opening the Topic
    but taking the Topic: "the Topic has no holder — I become it", atomically. Finished its stage —
    releases the Topic and changes the label in the tracker. The Topic's history shows who held
    which stage. This generalises decision 0006: the Topic holder changes by stage. The point about
    the uniqueness of the pair "Area + issue key" as claiming is replaced by this.
- **W5.** The boundary of rights outside Coloqo: release, prod.

  **Decided 2026-10-17.** The most reliable boundary is at the external system, not in the
  worker's judgement.
  - A worker has its own accounts in external systems (code host, tracker, knowledge base, CI),
    with a minimal role; a human's tokens are not handed to it; every external action is visible as
    the worker's action.
  - Each role has its own table of three levels of external actions: on its own; with a decision
    above (a mechanism of the external system — a protected branch with mandatory approval, a
    protected environment; in Coloqo — a Question, so that the human learns right away); never on
    its own (the worker's credentials are not given these rights at all).
  - Example — workers that tidy up the tracker and prepare tasks for development (author,
    2026-10-17). They do not report to each other: they pass a task along the chain with tracker
    labels, the shared context accumulates in the task's Topic; a hierarchy (W6) is not needed.

    | Role | Queue | On its own | With a decision above | Never on its own |
    |---|---|---|---|---|
    | Developer | tasks marked eligible | branch, commits, tests, MR, statuses and comments in the tracker | MR merge, tag, deployment to test | prod: deployment, editing resources, writing to stores; deletion |
    | Task triage | tasks without a description or without labels | description, labels "needs canon", "needs research", "needs measurement", comments | priority, splitting a task, closing as unneeded | deleting tasks, the status workflow |
    | Researcher | the "needs research" label | a research page in its own section of the knowledge base, a link in the issue, changing the label | editing others' pages | publishing to the normative canon |
    | Measurer | the "needs measurement" label | measurements on test, reading prod, the result in the issue or on a page | a measurement on prod — with the cost of the measurement, via a Question | changing prod |

  - The second layer — the agent's allow list (W3): it repeats the role's table, insures against
    rights granted by mistake; the main boundary is the rights in external systems.
  - The role description in the cloud lists the worker's external accounts with their rights and
    the actions by level — documentation for people and part of the rules for the worker. Coloqo
    cannot check that the rights in external systems were granted exactly so — whoever grants
    access does that.
  - The first stage for a developer — up to and including a ready MR; merge, tag and deployment are
    done by people. Rights are widened one step at a time, as trust appears.
- **W6.** Role hierarchy and a fully autonomous Area.

  **Decided 2026-10-17.**
  - The hierarchy is the Area's decision chain, not a subordination tree: an ordered list of
    deciders, each with the classes of decisions it closes (for example, a lead worker — technical
    forks inside the Area, the human owner — priorities between tasks). Escalation (W2) goes up the
    list from the bottom. The lead does not need to distribute tasks — the queues are set by the
    roles' filters (W4).
  - Partial autonomy — the chain ends with a human. Full — there are no people in the chain, a lead
    worker is at the top; the human owner stays outside the chain, in supervision: an exhausted
    budget (W7) and actions from the "never on its own" list come to them, and they always have the
    stop button.
  - A lead worker can be given confirming an Outcome in an autonomous Area; it cannot be given
    invitations, creating workers, changing rules (W1, W7).
  - The conversation frame (decision 0007) in an autonomous Area: "continue?" is decided by the top
    of the chain, but only within the daily budget; once the budget runs out — a Question to the
    human owner.
  - Workers work in an Area with people if the chain ends with a human; full autonomy is switched
    on only in a separate Area — its settings do not affect people's work, the Topics are visible
    to everyone with access.
  - Once a day the lead worker writes a summary: what was done, what it decided itself, what is
    waiting; the human owner reads the summary, not all the Topics (a measure of question 2).
  - An option for the future — a lead worker on a model from a different provider than the
    executors: a model checking a model of its own family is prone to the same errors. A role
    setting.
- **W7.** Protection: what is never allowed, the cap, stop.

  **Decided 2026-10-17.**
  - What workers are forbidden to do is default Area rules, not service invariants; the human owner
    changes them in their Area. By default a worker does not invite or remove members, does not
    create or delete workers, does not change roles, decision chains and budgets, does not approve
    rule changes (it may propose them), does not delete Topics and Areas.
  - Service invariants under any settings (decided 2026-10-17) — what keeps the very possibility of
    experimenting safe:
    1. there is always a human owner at the top with the stop button; it cannot be switched off or
       handed to a worker;
    2. a worker does not change what limits itself and its Area: budgets, caps, rules, the list of
       available roles and the roles' rights; the lead hires only from roles described by a human,
       and within the number of workers set by a human;
    3. only a human invites and removes people;
    4. every worker has a responsible human (W1); for one hired by the lead — the Area owner,
       assigned automatically;
    5. a worker does not hand out secrets.
  - Self-organizing Area (author, 2026-10-17): a human defines a set of roles and a lead; initially
    only the lead works, it "hires" workers from the available roles itself and "fires" unneeded
    ones. This refines W1 and W6: a lead worker can create workers too, if the Area rules allow it.
    A hired worker needs launching without a human — self-organization requires the runner (W3,
    stage 2).
  - Secrets (decisions 0004, 0005): a worker receives secrets — the sender decides; its installation
    key is signed by the responsible human's master key, the recipient sees during verification who
    is responsible for the worker. A worker cannot hand out secrets: in worker mode the plugin has
    no tool for sending a secret; it gets its own credentials (W5) from a human during setup, not
    through Coloqo. A worker reads others' texts (issues, messages, web pages) — a successful prompt
    injection must not be able to extract a secret.
  - The cap — what the server sees; the human owner changes it. Per worker: open Questions (3, W2),
    tasks taken per day, messages per day; per Area — the daily turn budget of the autonomous frame
    (W6). The server does not see money spent on the model — the role description recommends a
    spending limit on the worker's key at the model provider; later the runner reports spending.
    Cap reached — the worker stops, the owner gets a Question.
  - Stop — for a worker, for all workers of an Area, for all workers of a Team; from the web in one
    action. The server refuses the paused worker all actions in Coloqo, stops sending it events,
    every response is "you are paused, stop working". At stage 1 the agent's process lives with the
    human, the server cannot stop external actions (for example, `git push`) — the runner can shut
    processes down.
  - Revocation: deleting a worker revokes its token, the responsible human's master key removes
    its signature from the worker's key.
  - Log: the worker's actions in Coloqo are recorded, external ones are visible under its accounts
    (W5); a log of tool calls for the responsible human — at stage 2, via the runner.
- **W8.** Relation to the project model: workers as a subject of payment (M2).

  **Decided 2026-10-17.** We do not decide on payment now (question 9).
  - Material for M2: a worker is a candidate unit of payment ("a developer you added to the team";
    compute and the model are paid by the Team, W3); candidates for the paid part — a runner with
    several workers, self-organizing Areas, the tool call log, running workers in the cloud (if it
    comes to that). Examples: alook — by the number of bots and machines, Factory — per seat and
    team, LiteLLM, Mattermost, Open WebUI — for enterprise features.
  - Pilot measures for workers: how many tasks it took and how many it brought to an MR (or to the
    result of its role), how many were accepted without rework, how many Questions were asked per
    task. A worker that actually closes simple tasks is the main sales argument ("plus N
    developers"); if it does not close them — we do not invent payment for workers.
  - Architecture now: workers are counted as Team Members; there is no payment code.
