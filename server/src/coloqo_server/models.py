"""The data model (decision 0008)."""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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
    """An Assistant: one Claude Code session of the User's agent in a project (decision 0024).

    Attributes:
        id: Identifier.
        key: Public identifier the plugin sends in ``X-Coloqo-Assistant`` (decision 0025).
        user_id: On whose behalf it acts.
        installation_id: The computer it runs on.
        project_id: The project.
        session_key: Hash of the Claude Code session id; empty for the one Assistant a plugin
            without sessions (0.4.0 and older) registers per project.
        session_id: The Claude Code session id, shown to its owner only.
        word: Its own word, unique among the project's live Assistants.
        name: Shown to the Team, ``alice · billing-api · vega``.
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
        archive_days: Days a closed Topic stays before deletion; ``None`` takes the instance's
            setting (decision 0021).
        last_topic: Number of its newest Topic; the next one gets ``last_topic + 1``.
        last_file: Number of its newest file, the same way.
        last_event: Number of its newest event, the same way (decision 0028).
        created_at: Creation time.
    """

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    turn_limit: Mapped[int] = mapped_column(Integer, default=10)
    archive_days: Mapped[int | None] = mapped_column(Integer)
    last_topic: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_file: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_event: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
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
        created_at: Creation time.
    """

    __tablename__ = "areas"
    __table_args__ = (UniqueConstraint("team_id", "name"), UniqueConstraint("team_id", "slug"))

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
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
    """A discussion of one question in an Area.

    Attributes:
        id: Identifier, never shown (decision 0025).
        team_id: The Team, denormalised for access checks.
        number: Its number in the Team, from 1 without gaps, shown as ``T-<number>``.
        area_id: The Area.
        title: One line: the question.
        issue: Tracker issue key or link, if the Topic is for one.
        status: Open or closed.
        outcome: How it was settled, with a link to the MR or issue.
        created_by: The User who opened it.
        holder_assistant_id: The Assistant that holds it (decision 0006).
        last_number: Number of the newest Message; the next one gets ``last_number + 1``.
        turns_since_human: Assistants' turns since the last human Message (decision 0007).
        created_at: Creation time.
        updated_at: Time of the newest Message.
        closed_at: When it was closed; ``None`` while open. The archive time runs from it.
        idle_warned_at: When its people were told it would close for inactivity; cleared by a
            new Message.
        deleted_at: When its Messages and files were deleted; the row stays as its card.
    """

    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("team_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
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
