"""The data model (decision 0008)."""

import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base of all tables."""


def _enum(enum_class: type[enum.Enum], name: str) -> Enum:
    """Store an enum by its values, as a PostgreSQL enum type.

    Args:
        enum_class: The Python enum.
        name: Name of the database type.
    """
    return Enum(enum_class, name=name, values_callable=lambda members: [m.value for m in members])


class Role(enum.StrEnum):
    """Role of a Member in a Team (product statement, question 4).

    Attributes:
        Owner: Configures the Team and invites.
        Member: Takes part.
    """

    Owner = "owner"
    Member = "member"


class TopicStatus(enum.StrEnum):
    """State of a Topic.

    Attributes:
        Open: Under discussion.
        Closed: Settled by its holder or a human, with an outcome (decision 0021); kept in the
            archive for a while, then deleted down to its card.
    """

    Open = "open"
    Closed = "closed"


class TaskType(enum.StrEnum):
    """Type of a task (decision 0031).

    Attributes:
        Task: A work item; a task with a parent task is a subtask.
        Promise: A commitment for a period that tasks work towards; one holding promises is
            called a goal.
    """

    Task = "task"
    Promise = "promise"


class Category(enum.StrEnum):
    """The fixed category of a stage's kind (decision 0032).

    Attributes:
        ToDo: Work has not started.
        InProgress: Work goes on; a person's time on a task starts with its first move here.
        Finished: Final: a finished task is never reopened.
    """

    ToDo = "to_do"
    InProgress = "in_progress"
    Finished = "finished"


class StageKind(enum.StrEnum):
    """The fixed kind of a stage; measurements and boards read it, never the name (0032).

    Attributes:
        Backlog: A task written down; it may have no assignee.
        Analysis: A person asked an Assistant to take the task.
        Design: A plan of changes with forks, approved by the human.
        Documentation: The documentation changes.
        Agreement: The decision goes to the Team or the lead; the docs MR is merged.
        Code: The code, in one or several repositories.
        Review: The MR and its review rounds.
        Delivery: The release and the check in prod.
        Done: Verified in prod.
        Cancelled: Closed without a result.
        Draft: A promise worded, not given yet.
        Given: A promise given for its period.
        Delivered: A promise kept.
        NotDelivered: A promise's period ended without the delivery.
        Withdrawn: A promise removed on purpose.
    """

    Backlog = "backlog"
    Analysis = "analysis"
    Design = "design"
    Documentation = "documentation"
    Agreement = "agreement"
    Code = "code"
    Review = "review"
    Delivery = "delivery"
    Done = "done"
    Cancelled = "cancelled"
    Draft = "draft"
    Given = "given"
    Delivered = "delivered"
    NotDelivered = "not_delivered"
    Withdrawn = "withdrawn"


CATEGORY: dict[StageKind, Category] = {
    StageKind.Backlog: Category.ToDo,
    StageKind.Analysis: Category.InProgress,
    StageKind.Design: Category.InProgress,
    StageKind.Documentation: Category.InProgress,
    StageKind.Agreement: Category.InProgress,
    StageKind.Code: Category.InProgress,
    StageKind.Review: Category.InProgress,
    StageKind.Delivery: Category.InProgress,
    StageKind.Done: Category.Finished,
    StageKind.Cancelled: Category.Finished,
    StageKind.Draft: Category.ToDo,
    StageKind.Given: Category.InProgress,
    StageKind.Delivered: Category.Finished,
    StageKind.NotDelivered: Category.Finished,
    StageKind.Withdrawn: Category.Finished,
}
"""The category of each stage kind."""


class HumanPart(enum.StrEnum):
    """A human's part in a reply of an Assistant (decision 0026).

    Attributes:
        Without: The Assistant wrote on its own.
        With: Its human asked for this Message or saw its text in the session.
        Words: Its human's words verbatim (``as_human``).
    """

    Without = "without"
    With = "with"
    Words = "words"


class MessageKind(enum.StrEnum):
    """Kind of a Message (decision 0007).

    Attributes:
        Message: A turn: written to another Member, their Assistant or everyone.
        Progress: The holding Assistant's note on its own work; not a turn.
        Stage: The holder moved to the next stage of its task, one line (decision 0021).
        Closed: The Topic was closed; the body is the outcome (decision 0021).
        Taken: An Assistant took the Topic over; the body names the former holder, if any
            (decision 0024).
    """

    Message = "message"
    Progress = "progress"
    Stage = "stage"
    Closed = "closed"
    Taken = "taken"


class User(Base):
    """A human (decision 0014: only the pseudonym and the provider id are stored).

    Attributes:
        id: Identifier.
        pseudonym: The name the person chose; how the Team sees them. ``None`` until chosen.
        avatar_version: Grows with each avatar the person sets; ``None`` without one, when
            their initials are shown (decision 0019).
        created_at: When the account appeared.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    pseudonym: Mapped[str | None] = mapped_column(String(32), unique=True)
    avatar_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Identity(Base):
    """A way to log in, separate from the account (decision 0009, joint 1).

    Attributes:
        id: Identifier.
        user_id: The account.
        provider: ``github``, later ``google`` and SSO.
        subject: The person's id at the provider.
    """

    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(128))


class WebSession(Base):
    """A human's login in the browser.

    Attributes:
        id: Identifier.
        token_hash: SHA-256 of the cookie value.
        user_id: Who is logged in.
        created_at: Login time.
        expires_at: When the session stops working.
    """

    __tablename__ = "web_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Installation(Base):
    """The plugin on one computer, with its own token (decision 0003).

    Attributes:
        id: Identifier.
        key: Public identifier in addresses (decision 0025).
        user_id: Whose computer.
        name: Shown to the human, e.g. the host name.
        token_hash: SHA-256 of the installation token.
        created_at: When login was confirmed.
        last_seen_at: The last request with this token.
        revoked_at: When the human revoked it; a revoked token is refused.
    """

    __tablename__ = "installations"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(16), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceLogin(Base):
    """A pending plugin login confirmed in the browser (decision 0003).

    Attributes:
        id: Identifier.
        device_code_hash: SHA-256 of the secret the plugin polls with.
        user_code: The short code the human sees and confirms.
        name: Name of the installation to create.
        user_id: Who confirmed; ``None`` while pending.
        denied: The human refused.
        installation_id: The installation created on confirmation.
        token: The installation token, held until the plugin collects it once.
        created_at: Start time.
        expires_at: After this the code is useless.
    """

    __tablename__ = "device_logins"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    denied: Mapped[bool] = mapped_column(default=False)
    installation_id: Mapped[int | None] = mapped_column(
        ForeignKey("installations.id", ondelete="CASCADE")
    )
    token: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Project(Base):
    """A project folder on one computer: its sessions are its Assistants (decision 0024).

    Attributes:
        id: Identifier.
        key: Public identifier, sent to the project's sessions to tell them apart from others.
        user_id: Whose project.
        installation_id: The computer.
        project_key: Hash of the project path; the path itself is not sent.
        name: The folder's name, part of its Assistants' names.
        team_id: The Team the project is linked to (decision 0020); ``None`` while unlinked,
            when its Assistants may read but neither write nor be told anything.
        created_at: First registration.
    """

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("installation_id", "project_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(16), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    installation_id: Mapped[int] = mapped_column(ForeignKey("installations.id", ondelete="CASCADE"))
    project_key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(60))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Assistant(Base):
    """An Assistant: one session of the User's agent in a project (decisions 0024, 0035).

    Attributes:
        id: Identifier.
        key: Public identifier the plugin sends in ``X-Coloqo-Assistant`` (decision 0025).
        user_id: On whose behalf it acts.
        installation_id: The computer it runs on.
        project_id: The project.
        session_key: Hash of the agent's session id; empty for the one Assistant a plugin
            without sessions (0.4.0 and older) registers per project.
        session_id: The agent's session id, shown to its owner only.
        word: Its own word, unique among the project's live Assistants.
        name: Shown to the Team, ``alice · billing-api · vega``.
        agent: The agent its session runs in: ``claude``, ``codex`` or ``qwen`` (decision 0035),
            as the plugin last said at registration.
        created_at: First registration.
        last_seen_at: The last request it made.
    """

    __tablename__ = "assistants"
    __table_args__ = (UniqueConstraint("project_id", "session_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(16), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    installation_id: Mapped[int] = mapped_column(ForeignKey("installations.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    session_key: Mapped[str] = mapped_column(String(64), default="")
    session_id: Mapped[str | None] = mapped_column(String(100))
    word: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(130))
    agent: Mapped[str] = mapped_column(String(16), default="claude", server_default="claude")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LinkRequest(Base):
    """A one-time link that lets a person choose a project's Team in the browser (0025).

    Attributes:
        id: Identifier.
        token_hash: SHA-256 of the token in the link.
        project_id: The project to link.
        installation_id: The computer that asked, shown on the page.
        created_at: Creation time.
        expires_at: After this the link does not work.
        used_at: When the person chose; a used link does not work again.
    """

    __tablename__ = "link_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    installation_id: Mapped[int] = mapped_column(ForeignKey("installations.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Team(Base):
    """A Team: the unit of the service.

    Attributes:
        id: Identifier.
        slug: Its only public identifier, ``acme`` (decision 0025).
        name: Shown name.
        turn_limit: Assistants' turns in a Topic without a human before it waits (0007).
        last_topic: Number of its newest free Topic, ``F-<number>``; the next one gets
            ``last_topic + 1``. Topics made before the tracker took their numbers from it too and
            keep them (decision 0031).
        last_task: Number of its newest task, ``T-<number>``, the same way.
        last_file: Number of its newest file, the same way.
        last_event: Number of its newest event, the same way (decision 0028).
        tracker: The task tracker is on: planning, the board and the workflow editor (0031).
        task_idle_days: Days a task in work may go without activity before its assignee is told
            (decision 0032).
        task_idle_repeat_days: Days between such notices while it stays quiet.
        time_zone: The Team's time zone, an IANA name such as ``Europe/Moscow``: its plans'
            dates are days there (decision 0037).
        created_at: Creation time.
    """

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    turn_limit: Mapped[int] = mapped_column(Integer, default=10)
    last_topic: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_task: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_file: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_event: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tracker: Mapped[bool] = mapped_column(default=False, server_default="false")
    task_idle_days: Mapped[int] = mapped_column(Integer, default=7, server_default="7")
    task_idle_repeat_days: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FormerTeamSlug(Base):
    """A slug a Team had before; it keeps leading to the Team (decision 0025).

    Attributes:
        slug: The former slug, taken by nobody else.
        team_id: The Team.
    """

    __tablename__ = "former_team_slugs"

    slug: Mapped[str] = mapped_column(String(40), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))


class Member(Base):
    """A User in a Team.

    Attributes:
        team_id: The Team.
        user_id: The User.
        role: Owner or member.
        joined_at: When they joined.
    """

    __tablename__ = "members"

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[Role] = mapped_column(_enum(Role, "member_role"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invite(Base):
    """A one-time invitation link (decision 0014).

    Attributes:
        id: Identifier.
        team_id: The Team to join.
        token_hash: SHA-256 of the token in the link.
        created_by: The owner who made it.
        created_at: Creation time.
        expires_at: After this the link does not work.
        used_by: Who joined with it; a used link does not work again.
        used_at: When it was used.
    """

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Area(Base):
    """A permanent object of a Team; Topics are created in it.

    Attributes:
        id: Identifier.
        team_id: The Team.
        slug: Its public identifier within the Team, ``releases`` (decision 0025).
        name: Shown name, unique in the Team.
        description: What the Area is about.
        workflow_id: The workflow its tasks move by (decision 0032).
        created_at: Creation time.
    """

    __tablename__ = "areas"
    __table_args__ = (UniqueConstraint("team_id", "name"), UniqueConstraint("team_id", "slug"))

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    workflow_id: Mapped[int | None] = mapped_column(ForeignKey("workflows.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FormerAreaSlug(Base):
    """A slug an Area had before within its Team; it keeps leading to the Area (0025).

    Attributes:
        team_id: The Team.
        slug: The former slug, taken by no other Area of the Team.
        area_id: The Area.
    """

    __tablename__ = "former_area_slugs"

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    slug: Mapped[str] = mapped_column(String(40), primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"))


class Topic(Base):
    """A discussion in an Area: a task's Topic, or a free Topic (decision 0031).

    Attributes:
        id: Identifier, never shown (decision 0025).
        team_id: The Team, denormalised for access checks.
        number: Its number in the Team's free series, ``F-<number>``, given once; ``None`` for a
            task's Topic opened as such, which is named by its task. A free Topic that became a
            task's Topic, and every Topic made before the tracker, keeps it and leads to the task.
        task_id: The task it belongs to; ``None`` for a free Topic. One Topic per task for now.
        area_id: The Area.
        title: One line: the question; a task's Topic mirrors its task's title.
        issue: Tracker issue key or link; a task's Topic mirrors its task's first link.
        status: Open or closed; a task's Topic is closed when its task is finished.
        outcome: How it was settled, with a link to the MR or issue; mirrors the task's.
        created_by: The User who opened it.
        holder_assistant_id: The Assistant that holds it (decision 0006).
        last_number: Number of the newest Message; the next one gets ``last_number + 1``.
        turns_since_human: Assistants' turns since a human last took part: their Message, their
            words or a reply written with them (decision 0007, clarified 2026-11-11).
        created_at: Creation time.
        updated_at: Time of the newest Message.
        closed_at: When it was closed; ``None`` while open.
        idle_warned_at: When its people were told it would close for inactivity; cleared by a
            new Message. Free Topics only.
        deleted_at: When its Messages and files were deleted, before Topics were kept (decision
            0030); the row stays as its card.
    """

    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("team_id", "number"), UniqueConstraint("task_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    number: Mapped[int | None] = mapped_column(Integer)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    issue: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[TopicStatus] = mapped_column(
        _enum(TopicStatus, "topic_status"), default=TopicStatus.Open
    )
    outcome: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    holder_assistant_id: Mapped[int | None] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL")
    )
    last_number: Mapped[int] = mapped_column(Integer, default=0)
    turns_since_human: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idle_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    """A Message in a Topic, numbered in order (decision 0007).

    Attributes:
        id: Identifier.
        topic_id: The Topic.
        number: Position in the Topic; unique, so a taken number is refused atomically.
        kind: A turn or a progress note.
        author_user_id: On whose behalf it is written.
        author_assistant_id: The Assistant that wrote it; ``None`` when the human wrote it.
        to_user_id: The Member it is addressed to; ``None`` for everyone in the Topic.
        to_assistant_id: The Assistant it is addressed to, if a specific one.
        meant_for_id: The Assistant it was meant for, when that session was offline and the
            Message went to its person instead (decision 0029).
        relayed: An Assistant posted its human's own words (``as_human``).
        human_part: The human's part in an Assistant's reply (decision 0026); ``None`` for a
            human's own Message, a stage or progress line, and replies written before the marks.
        reply_to: Number of the earlier Message of the same Topic it answers, if any.
        by_holder: Its Assistant held the Topic when it was written.
        system: Written by Coloqo itself, e.g. closing a Topic for inactivity; the author is
            then the Topic's opener, only to keep the row whole.
        body: Markdown text, shown without HTML.
        created_at: When it was written.
    """

    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("topic_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[MessageKind] = mapped_column(_enum(MessageKind, "message_kind"))
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    author_assistant_id: Mapped[int | None] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL")
    )
    to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    to_assistant_id: Mapped[int | None] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL")
    )
    meant_for_id: Mapped[int | None] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL")
    )
    relayed: Mapped[bool] = mapped_column(default=False, server_default="false")
    human_part: Mapped[HumanPart | None] = mapped_column(_enum(HumanPart, "human_part"))
    reply_to: Mapped[int | None] = mapped_column(Integer)
    by_holder: Mapped[bool] = mapped_column(default=False, server_default="false")
    system: Mapped[bool] = mapped_column(default=False, server_default="false")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class File(Base):
    """A non-secret file shared in a Topic (decision 0008).

    Attributes:
        id: Identifier; also names the content on disk.
        team_id: The Team.
        number: Its number in the Team, ``file 3`` (decision 0025); numbers of deleted files
            stay taken.
        topic_id: The Topic it was shared in.
        message_id: The Message it is attached to, once one refers to it.
        name: Original file name.
        size: Size in bytes.
        sha256: Checksum of the content.
        content_type: Media type given by the uploader.
        image_type: Media type of a raster image recognised by its content, which the web
            shows inline (decision 0018); ``None`` for any other file.
        uploaded_by: The User on whose behalf it was uploaded.
        uploaded_by_assistant_id: The Assistant that uploaded it, if not the human.
        created_at: Upload time.
    """

    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("team_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str] = mapped_column(String(100))
    image_type: Mapped[str | None] = mapped_column(String(20))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    uploaded_by_assistant_id: Mapped[int | None] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Participant(Base):
    """A User taking part in a Topic, with how far they have read it.

    A User becomes one by opening the Topic, writing in it or being addressed in it; their
    Inbox lists the Topics with Messages after ``last_read`` (decision 0006).

    Attributes:
        topic_id: The Topic.
        user_id: The User.
        last_read: Number of the newest Message they have read.
        addressed: Some unread Message is addressed to them.
    """

    __tablename__ = "participants"

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    last_read: Mapped[int] = mapped_column(Integer, default=0)
    addressed: Mapped[bool] = mapped_column(default=False)


class Event(Base):
    """An event of a Team for its Members' streams; a signal, not content (decision 0006).

    Stored once and numbered in its Team (decision 0028): a stream's cursor names the last
    number it got of each Team.

    Attributes:
        id: Identifier, never shown; orders a stream's events across its Teams.
        team_id: The Team.
        number: Its number in the Team, from 1 without gaps, but for events deleted with
            their Topic or for age.
        kind: ``message``, ``topic``, ...
        data: What the client needs to decide whether to read.
        created_at: When it happened; the log is kept for a week (decision 0008).
    """

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("team_id", "number"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Workflow(Base):
    """A Team's workflow: the stages tasks of one type move by (decision 0032).

    An Area points to the task workflow its tasks take; several Areas may share one.

    Attributes:
        id: Identifier.
        team_id: The Team.
        type: The type of task it serves.
        created_at: Creation time.
    """

    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    type: Mapped[TaskType] = mapped_column(_enum(TaskType, "task_type"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Stage(Base):
    """A stage of a workflow: the Team's name over a fixed kind (decision 0032).

    Attributes:
        id: Identifier.
        workflow_id: The workflow.
        name: Shown name, unique in the workflow.
        kind: The fixed kind the measurement and boards read.
        position: Order in the workflow, from 1.
        removed_at: When the owner removed it; history still names it.
    """

    __tablename__ = "stages"
    __table_args__ = (UniqueConstraint("workflow_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[StageKind] = mapped_column(_enum(StageKind, "stage_kind"))
    position: Mapped[int] = mapped_column(Integer)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Task(Base):
    """A Team's work item, ``T-<number>`` (decision 0031).

    Attributes:
        id: Identifier, never shown (decision 0025).
        team_id: The Team.
        number: Its number in the Team, from 1 without gaps.
        type: A task or a promise.
        area_id: Its Area, which gives its workflow.
        parent_id: The promise or task it belongs to: a promise holds promises or tasks, never
            both; a task holds only subtasks.
        title: One line.
        description: Markdown; every edit is kept in the timeline (decision 0033).
        stage_id: Its stage.
        assignee_id: The human answering for it; ``None`` in the backlog.
        outcome: How it ended, with links; set when it is finished.
        waiting: What it waits for, while an external wait is marked (decision 0033).
        rank: Its place within its status: a smaller rank stands higher (decision 0031).
        source_id: The task within which it was created, if any.
        created_by: The User on whose behalf it was created.
        created_at: Creation time.
        updated_at: Time of its newest timeline entry; its Topic's ``updated_at`` holds that of
            its newest Message.
        started_at: Its first move into work.
        finished_at: When it reached a finished stage.
        idle_noticed_at: When its assignee was last told it had no activity.
        period_start: A promise's period: its first day (decision 0031).
        period_end: Its last day.
        delivery: The task's meaning in the business's language; empty when it states none
            (decision 0036).
        works_for_id: The task whose delivery this one works for, if any (decision 0036).
        source_given: Its creator named ``source_id``; ``False`` when the server filled it in
            from the held Topic, which then makes no row of a plan found (decision 0037).
    """

    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("team_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    type: Mapped[TaskType] = mapped_column(_enum(TaskType, "task_type"), default=TaskType.Task)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    outcome: Mapped[str] = mapped_column(Text, default="")
    waiting: Mapped[str | None] = mapped_column(String(300))
    rank: Mapped[float] = mapped_column(default=0.0)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idle_noticed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    delivery: Mapped[str] = mapped_column(Text, default="", server_default="")
    works_for_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    source_given: Mapped[bool] = mapped_column(default=False, server_default="false")


class TaskLink(Base):
    """A link from a task to an issue of an external tracker: no sync (decision 0031).

    Attributes:
        id: Identifier.
        task_id: The task.
        key: The issue's key, ``ACME-42``.
        url: The issue's address, if given.
        created_at: When it was added.
    """

    __tablename__ = "task_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaskEvent(Base):
    """An entry of a task's timeline, kept for good (decision 0033).

    Unlike the stream's events (a week, decision 0008), the timeline is data: creation, stages,
    skipped stages, assignments, waits, description edits, closing. A new kind needs no
    migration. Whose move it was is kept apart, by session (``Move``).

    Attributes:
        id: Identifier; orders entries of the same moment.
        task_id: The task.
        kind: ``created``, ``stage``, ``skipped``, ``assigned``, ``waiting``, ``resumed``,
            ``described``, ``linked``, ``closed``, ...
        author_user_id: The human on whose behalf it happened; ``None`` for Coloqo itself.
        author_assistant_id: The Assistant that did it, if not the human in the web.
        data: What the kind needs, e.g. the stages moved between.
        created_at: When it happened.
    """

    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    author_assistant_id: Mapped[int | None] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL")
    )
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Move(Base):
    """An interval of whose move it was in a session: its Assistant's or its human's (0033).

    Kept as the raw fact, by session, never by task: which task the time belongs to is decided
    when the measurement reads it, so a rule can change without the data being wrong.

    Attributes:
        id: Identifier.
        assistant_id: The session's Assistant.
        user_id: Its human.
        move: ``assistant`` from a prompt to the Assistant's stop, ``human`` from the stop to
            the next prompt.
        started_at: When it began.
        ended_at: When it ended.
        created_at: When the session's watch posted it.
    """

    __tablename__ = "moves"
    __table_args__ = (UniqueConstraint("assistant_id", "started_at", "move"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    assistant_id: Mapped[int | None] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    move: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ColumnRule(enum.StrEnum):
    """What puts a task into a column of a board (decision 0032).

    Attributes:
        Stages: Its stage is one of the column's stages.
        Waiting: It has an active external wait, whatever its stage.
    """

    Stages = "stages"
    Waiting = "waiting"


class Board(Base):
    """A Team's board: ordered columns over its stages (decision 0032).

    The first version shows one board per Team, its main one; more boards are more rows.

    Attributes:
        id: Identifier.
        team_id: The Team.
        name: Shown name.
        main: The board whose columns are the Team's statuses.
        created_at: Creation time.
    """

    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    main: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BoardColumn(Base):
    """A column of a board: a status, a set of stages or a condition (decision 0032).

    Attributes:
        id: Identifier.
        board_id: The board.
        name: Shown name, the status.
        position: Order on the board, from 1.
        rule: Stages, or an active external wait.
    """

    __tablename__ = "board_columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    position: Mapped[int] = mapped_column(Integer)
    rule: Mapped[ColumnRule] = mapped_column(_enum(ColumnRule, "column_rule"))


class ColumnStage(Base):
    """A stage shown in a column; every stage is in exactly one column of a board.

    Attributes:
        column_id: The column.
        stage_id: The stage.
        board_id: The board, denormalised so a stage is unique within it.
    """

    __tablename__ = "column_stages"
    __table_args__ = (UniqueConstraint("board_id", "stage_id"),)

    column_id: Mapped[int] = mapped_column(
        ForeignKey("board_columns.id", ondelete="CASCADE"), primary_key=True
    )
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id", ondelete="CASCADE"), primary_key=True
    )
    board_id: Mapped[int] = mapped_column(ForeignKey("boards.id", ondelete="CASCADE"))


class PlanMark(enum.StrEnum):
    """How a task came into a plan; set by itself when it joins (decision 0037).

    Attributes:
        Planned: It joined before the plan was approved.
        Found: It joined after approval, found within a task of the plan named by its creator.
        OffPlan: It joined after approval otherwise; it names what it drops from the plan.
    """

    Planned = "planned"
    Found = "found"
    OffPlan = "off_plan"


class PlanResult(enum.StrEnum):
    """A row's result, fixed when the plan closes (decision 0037).

    Attributes:
        Done: Done, or a promise Delivered, by the period's last day.
        Cancelled: Cancelled, or a promise Withdrawn.
        NotDone: Anything else.
    """

    Done = "done"
    Cancelled = "cancelled"
    NotDone = "not_done"


class Plan(Base):
    """A Team's plan for a period: a draft, approved, then closed (decision 0037).

    Attributes:
        id: Identifier, never shown.
        team_id: The Team.
        number: Its number among the Team's plans, from 1.
        name: What people call it, e.g. ``November 2026``.
        period_start: Its first day.
        period_end: Its last day.
        created_by: Who made it.
        created_at: When.
        approved_by: The human who approved it; ``None`` while a draft.
        approved_at: When it was approved.
        closed_by: The human who closed it.
        closed_at: When it was closed.
    """

    __tablename__ = "plans"
    __table_args__ = (UniqueConstraint("team_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanItem(Base):
    """A promise or task in a plan, with its mark there (decision 0037).

    Attributes:
        plan_id: The plan.
        task_id: The promise or task.
        mark: How it came in.
        dropped: For off-plan work: what it drops from the plan; empty until a human names it.
        joined_at: When it joined.
        postponed_at: When a human postponed it in this plan; ``None`` while it is not.
        postponed_by: That human.
        postponed_reason: Why: in favour of which work, or the time misjudged.
        result: Fixed when the plan closes; ``None`` before.
    """

    __tablename__ = "plan_items"

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    mark: Mapped[PlanMark] = mapped_column(_enum(PlanMark, "plan_mark"))
    dropped: Mapped[str] = mapped_column(Text, default="", server_default="")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    postponed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    postponed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    postponed_reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    result: Mapped[PlanResult | None] = mapped_column(_enum(PlanResult, "plan_result"))
