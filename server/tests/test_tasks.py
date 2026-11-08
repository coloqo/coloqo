"""Tests of the tracker: tasks, stages, waits, closing, planning, names (decisions 0031-0033)."""

from collections.abc import Callable
from datetime import timedelta

import pytest

from coloqo_server.security import now
from tests.conftest import Plugin, Setup

NEW = "0.7.0"
"""A plugin release that knows tasks and free Topics."""


@pytest.fixture
def new(setup: Setup, plugin: Callable[..., Plugin]) -> tuple[Plugin, Plugin]:
    """Give Alice and Bob Assistants of a plugin that knows tasks.

    Args:
        setup: The Team.
        plugin: Factory of plugin installations.
    """
    return (
        plugin(setup.alice, "billing-api", setup.team, session="n1", version=NEW),
        plugin(setup.bob, "web", setup.team, session="n2", version=NEW),
    )


def _task(setup: Setup, assistant: Plugin, title: str = "Rename field amount") -> dict:
    """Open a Topic for a new task, as new work with no task.

    Args:
        setup: The Team.
        assistant: The Assistant opening it.
        title: The task's title.
    """
    response = assistant.client.post(
        f"/api/team/{setup.team}/topic",
        json={"area": setup.area, "title": title, "body": "Taking it", "issue": "ACME-42"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _path(setup: Setup, number: int) -> str:
    """Return a task's address in the API.

    Args:
        setup: The Team.
        number: The task's number.
    """
    return f"/api/team/{setup.team}/task/{number}"


def _tracker(setup: Setup) -> None:
    """Turn the Team's tracker on.

    Args:
        setup: The Team.
    """
    response = setup.alice.patch(f"/api/team/{setup.team}", json={"tracker": True})
    assert response.json()["tracker"] is True


def test_opening_a_topic_for_work_creates_a_task_in_work(
    setup: Setup, new: tuple[Plugin, Plugin]
) -> None:
    """A Topic for new work is a task in its first stage of work, assigned to the opener's human.

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    opened = _task(setup, alice)
    task = setup.alice.get(_path(setup, opened["number"])).json()

    assert (opened["kind"], opened["ref"], opened["stage"]) == ("task", "T-1", "Analysis")
    assert (task["assignee"], task["category"], task["has_topic"]) == (
        "alice",
        "in_progress",
        True,
    )
    assert task["links"] == [{"key": "ACME-42", "url": ""}]
    assert task["started_at"] is not None
    assert [e["kind"] for e in task["timeline"]] == ["created", "stage", "assigned", "linked"]
    assert task["topic"]["messages"][0]["body"] == "Taking it"


def test_free_topics_and_tasks_are_numbered_apart(setup: Setup, new: tuple[Plugin, Plugin]) -> None:
    """A free Topic is F-1 even after tasks T-1 and T-2; each series has its own counter.

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    _task(setup, alice)
    _task(setup, alice, "Second")
    free = alice.client.post(
        f"/api/team/{setup.team}/topic",
        json={"area": setup.area, "title": "Date format?", "body": "?", "free": True},
    ).json()
    listed = setup.alice.get(f"/api/team/{setup.team}/topic", params={"kind": "free"}).json()

    assert (free["kind"], free["ref"], free["number"], free["task"]) == ("free", "F-1", 1, None)
    assert [t["ref"] for t in listed] == ["F-1"]
    assert setup.alice.get(f"/api/team/{setup.team}/topic/1").json()["ref"] == "F-1"
    assert setup.alice.get(f"/api/team/{setup.team}/task/1/topic").json()["ref"] == "T-1"


def test_an_old_plugin_sees_no_free_topic(setup: Setup, new: tuple[Plugin, Plugin]) -> None:
    """A plugin older than the tracker reads /topic/N as T-N and never sees a free Topic.

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    _task(setup, alice)
    alice.client.post(
        f"/api/team/{setup.team}/topic",
        json={"area": setup.area, "title": "Date format?", "body": "?", "to": "bob", "free": True},
    )
    old = setup.bob_web.client

    listed = old.get(f"/api/team/{setup.team}/topic").json()
    inbox = old.get("/api/inbox").json()
    read = old.get(f"/api/team/{setup.team}/topic/1").json()
    asked_free = old.post(
        f"/api/team/{setup.team}/topic",
        json={"area": setup.area, "title": "Q", "body": "?", "free": True},
    ).json()

    assert [t["ref"] for t in listed] == ["T-1"]
    assert inbox == []
    assert read["ref"] == "T-1"
    assert asked_free["ref"] == "T-2"


def test_planning_needs_the_tracker(setup: Setup, new: tuple[Plugin, Plugin]) -> None:
    """Without the tracker no backlog and no assigning; with it, both (decision 0032).

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    number = _task(setup, alice)["number"]
    body = {"area": setup.area, "title": "Found along the way"}

    refused = alice.client.post(f"/api/team/{setup.team}/task", json=body)
    unassign = setup.alice.post(f"{_path(setup, number)}/assign", json={"assignee": "bob"})
    _tracker(setup)
    created = alice.client.post(f"/api/team/{setup.team}/task", json=body)

    assert refused.json()["detail"]["code"] == "no_tracker"
    assert unassign.json()["detail"]["code"] == "no_tracker"
    assert created.status_code == 201, created.text
    task = created.json()
    assert (task["stage"], task["category"], task["assignee"]) == ("Backlog", "to_do", None)
    assert task["source"] == number
    assert task["timeline"][0]["data"]["source"] == number


def test_taking_a_task_assigns_moves_and_opens_its_topic(
    setup: Setup, new: tuple[Plugin, Plugin]
) -> None:
    """Taking a backlog task assigns it, moves it to work and opens its Topic; a task planned
    for another human is taken only by an explicit reassignment.

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, bob = new
    _tracker(setup)
    free = setup.alice.post(
        f"/api/team/{setup.team}/task", json={"area": setup.area, "title": "Free one"}
    ).json()
    planned = setup.alice.post(
        f"/api/team/{setup.team}/task",
        json={"area": setup.area, "title": "Bob's", "assignee": "bob"},
    ).json()

    taken = bob.client.post(f"{_path(setup, free['number'])}/take", json={}).json()
    refused = alice.client.post(f"{_path(setup, planned['number'])}/take", json={})
    reassigned = alice.client.post(
        f"{_path(setup, planned['number'])}/take", json={"reassign": True, "body": "Mine now"}
    ).json()

    assert (taken["assignee"], taken["stage"], taken["holder"]) == (
        "bob",
        "Analysis",
        bob.assistant,
    )
    assert taken["topic"]["messages"][0]["body"] == f"Took T-{free['number']}: Free one"
    assert refused.json()["detail"]["code"] == "assigned"
    assert (reassigned["assignee"], reassigned["topic"]["messages"][0]["body"]) == (
        "alice",
        "Mine now",
    )


def test_only_the_assignee_s_assistant_moves_a_task(
    setup: Setup, new: tuple[Plugin, Plugin]
) -> None:
    """Stages move by the assignee's Assistant; another Assistant or a human cannot (0032).

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, bob = new
    number = _task(setup, alice)["number"]
    move = {"stage": "design"}

    by_bob = bob.client.post(f"{_path(setup, number)}/stage", json=move)
    by_human = setup.alice.post(f"{_path(setup, number)}/stage", json=move)
    unknown = alice.client.post(f"{_path(setup, number)}/stage", json={"stage": "Testing"})
    to_done = alice.client.post(f"{_path(setup, number)}/stage", json={"stage": "Done"})
    moved = alice.client.post(f"{_path(setup, number)}/stage", json=move)

    assert by_bob.json()["detail"]["code"] == "not_assignee"
    assert by_human.status_code == 403
    assert unknown.status_code == 422 and "Backlog, Analysis" in unknown.json()["detail"]
    assert to_done.status_code == 422
    assert (moved.json()["stage"], moved.json()["stage_kind"]) == ("Design", "design")


def test_a_skipped_stage_is_kept_with_its_reason(setup: Setup, new: tuple[Plugin, Plugin]) -> None:
    """Passing a stage at once leaves it in the timeline and the Topic's feed (decision 0032).

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    number = _task(setup, alice)["number"]
    path = _path(setup, number)
    alice.client.post(f"{path}/stage", json={"stage": "Design"})

    moved = alice.client.post(
        f"{path}/stage",
        json={
            "stage": "Agreement",
            "skip": {"Documentation": "no documentation changes"},
            "comment": "asked the lead",
        },
    )
    back = alice.client.post(f"{path}/stage", json={"stage": "Design"})
    task = setup.alice.get(path).json()

    assert moved.status_code == 200, moved.text
    assert back.status_code == 200
    skipped = [e for e in task["timeline"] if e["kind"] == "skipped"]
    assert [(e["data"]["stage"], e["data"]["reason"]) for e in skipped] == [
        ("Documentation", "no documentation changes")
    ]
    lines = [m["body"] for m in task["topic"]["messages"] if m["kind"] == "stage"]
    assert lines == [
        "Design",
        "Agreement (skipped Documentation: no documentation changes) — asked the lead",
        "Design",
    ]


def test_a_wait_stays_over_the_stage(setup: Setup, new: tuple[Plugin, Plugin]) -> None:
    """A wait is a mark over the stage, with its start, end and reason (decision 0033).

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    number = _task(setup, alice)["number"]
    path = _path(setup, number)

    waiting = alice.client.post(f"{path}/wait", json={"what": "a token from infra"}).json()
    resumed = alice.client.post(f"{path}/resume").json()
    task = setup.alice.get(path).json()

    assert (waiting["stage"], waiting["waiting"]) == ("Analysis", "a token from infra")
    assert (resumed["stage"], resumed["waiting"]) == ("Analysis", None)
    assert [e["kind"] for e in task["timeline"]][-2:] == ["waiting", "resumed"]


def test_a_finished_task_is_final(setup: Setup, new: tuple[Plugin, Plugin]) -> None:
    """Closing finishes the task and its Topic; then nothing moves it (decision 0032).

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    done = _task(setup, alice)["number"]
    cancelled = _task(setup, alice, "Not needed")["number"]

    no_outcome = alice.client.post(f"{_path(setup, done)}/close", json={"outcome": " "})
    closed = alice.client.post(
        f"{_path(setup, done)}/close", json={"outcome": "Merged in !17"}
    ).json()
    dropped = alice.client.post(
        f"{_path(setup, cancelled)}/close", json={"outcome": "Dup of T-1", "cancelled": True}
    ).json()
    again = alice.client.post(f"{_path(setup, done)}/close", json={"outcome": "x"})
    moved = alice.client.post(f"{_path(setup, done)}/stage", json={"stage": "Code"})
    taken = alice.client.post(f"{_path(setup, done)}/take", json={})
    message = setup.bob.post(f"{_path(setup, done)}/message", json={"number": 3, "body": "Why?"})
    task = setup.alice.get(_path(setup, done)).json()

    assert no_outcome.status_code == 422
    assert (closed["stage"], closed["outcome"], closed["finished_at"] is not None) == (
        "Done",
        "Merged in !17",
        True,
    )
    assert (dropped["stage"], dropped["category"]) == ("Cancelled", "finished")
    assert again.json()["detail"]["code"] == "finished"
    assert moved.json()["detail"]["code"] == "finished"
    assert taken.json()["detail"]["code"] == "finished"
    assert message.status_code == 201
    assert (task["stage"], task["topic"]["status"]) == ("Done", "closed")


def test_the_description_keeps_its_history(setup: Setup, new: tuple[Plugin, Plugin]) -> None:
    """Every edit of the description is a timeline entry with the text (decision 0033).

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    number = _task(setup, alice)["number"]
    path = _path(setup, number)

    alice.client.patch(path, json={"description": "Rename amount"})
    setup.alice.patch(path, json={"description": "Rename amount to total", "title": "Rename"})
    task = setup.alice.get(path).json()
    topic = setup.alice.get(f"{path}/topic").json()

    texts = [e["data"]["text"] for e in task["timeline"] if e["kind"] == "described"]
    assert texts == ["Rename amount", "Rename amount to total"]
    assert (task["description"], task["title"], topic["title"]) == (
        "Rename amount to total",
        "Rename",
        "Rename",
    )


def test_a_human_orders_tasks(setup: Setup, new: tuple[Plugin, Plugin]) -> None:
    """A human places a task above another; an Assistant cannot (decision 0032).

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    _tracker(setup)
    for title in ("one", "two", "three"):
        setup.alice.post(f"/api/team/{setup.team}/task", json={"area": setup.area, "title": title})

    by_assistant = alice.client.post(f"{_path(setup, 3)}/order", json={"before": 1})
    setup.alice.post(f"{_path(setup, 3)}/order", json={"before": 1})
    setup.alice.post(f"{_path(setup, 1)}/order", json={"after": 2})
    listed = setup.alice.get(f"/api/team/{setup.team}/task").json()

    assert by_assistant.status_code == 403
    assert [t["title"] for t in listed] == ["three", "two", "one"]


def test_a_promise_holds_promises_or_tasks(setup: Setup) -> None:
    """A promise holds either promises or tasks; a task only subtasks, one level (0031).

    Args:
        setup: The Team.
    """
    _tracker(setup)

    def create(title: str, type_: str = "task", parent: int | None = None) -> dict:
        """Create a task in the backlog by Alice in the web.

        Args:
            title: Its title.
            type_: ``task`` or ``promise``.
            parent: Its parent's number.
        """
        return setup.alice.post(
            f"/api/team/{setup.team}/task",
            json={"area": setup.area, "title": title, "type": type_, "parent": parent},
        ).json()

    goal = create("Billing by December", "promise")
    promise = create("Invoices", "promise", goal["number"])
    task = create("API", parent=promise["number"])
    subtask = create("Schema", parent=task["number"])
    mixed = create("Loose task", parent=goal["number"])
    deeper = create("Too deep", parent=subtask["number"])
    promise_under_task = create("Wrong", "promise", task["number"])

    assert (goal["stage"], goal["type"]) == ("Draft", "promise")
    assert (promise["parent"], task["parent"], subtask["parent"]) == (
        goal["number"],
        promise["number"],
        task["number"],
    )
    assert "never both" in mixed["detail"]
    assert "subtask holds nothing" in deeper["detail"]
    assert "only subtasks" in promise_under_task["detail"]


def test_moves_go_to_the_tasks_the_session_holds(setup: Setup, new: tuple[Plugin, Plugin]) -> None:
    """Move intervals land on the unfinished tasks whose Topics the session holds (0033).

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    held = _task(setup, alice)["number"]
    finished = _task(setup, alice, "Done one")["number"]
    alice.client.post(f"{_path(setup, finished)}/close", json={"outcome": "done"})
    start = now() - timedelta(minutes=30)
    intervals = [
        {
            "move": "assistant",
            "start": start.isoformat(),
            "end": (start + timedelta(minutes=5)).isoformat(),
        },
        {
            "move": "human",
            "start": (start + timedelta(minutes=5)).isoformat(),
            "end": (start + timedelta(minutes=20)).isoformat(),
        },
        {
            "move": "human",
            "start": start.isoformat(),
            "end": (start - timedelta(minutes=1)).isoformat(),
        },
        {
            "move": "human",
            "start": (start - timedelta(hours=13)).isoformat(),
            "end": start.isoformat(),
        },
    ]

    recorded = alice.client.post("/api/moves", json={"intervals": intervals}).json()
    by_human = setup.alice.post("/api/moves", json={"intervals": intervals})
    timeline = setup.alice.get(_path(setup, held)).json()["timeline"]

    assert recorded == {"recorded": 2, "tasks": [f"T-{held}"]}
    assert by_human.status_code == 403
    assert "move" not in [e["kind"] for e in timeline]


def test_the_workflow_lists_its_stages(setup: Setup) -> None:
    """A Team has the built-in task and promise workflows; its Areas use the task one (0032).

    Args:
        setup: The Team.
    """
    setup.alice.post(f"/api/team/{setup.team}/area", json={"name": "Design"})

    workflows = setup.alice.get(f"/api/team/{setup.team}/workflow").json()

    task, promise = workflows
    assert [s["name"] for s in task["stages"]] == [
        "Backlog",
        "Analysis",
        "Design",
        "Documentation",
        "Agreement",
        "Code",
        "Review",
        "Delivery",
        "Done",
        "Cancelled",
    ]
    assert sorted(task["areas"]) == [setup.area, "design"]
    assert [s["name"] for s in promise["stages"]] == [
        "Draft",
        "Given",
        "Delivered",
        "Not delivered",
        "Withdrawn",
    ]


def test_the_briefing_names_the_stages_and_the_tracker(
    setup: Setup, new: tuple[Plugin, Plugin]
) -> None:
    """A new plugin's briefing names the Team's stages, the backlog when the tracker is on, and
    the held task's stage; an old plugin keeps the rules it knows.

    Args:
        setup: The Team.
        new: Assistants of the new plugin.
    """
    alice, _ = new
    number = _task(setup, alice)["number"]
    before = alice.client.get("/api/briefing").json()["text"]
    _tracker(setup)
    after = alice.client.get("/api/briefing").json()["text"]
    old = setup.alice_api.client.get("/api/briefing").json()["text"]

    assert "Backlog → Analysis → Design" in before
    assert "has no tracker: no backlog" in before
    assert "create_task" in after
    assert f"T-{number} «Rename field amount» [ACME-42], stage Analysis" in after
    assert "/team/acme/task/12" in after
    assert "note_stage" in old and "change_stage" not in old
