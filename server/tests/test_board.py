"""Tests of the board, its columns, the workflow editor and promises (decisions 0031, 0032)."""

from collections.abc import Callable
from datetime import timedelta

import pytest

from coloqo_server.security import now
from coloqo_server.settings import Settings
from tests.conftest import Plugin, Setup, _connect

NEW = "0.8.0"
"""A plugin release that knows tasks, free Topics and promises."""


@pytest.fixture
def alice(setup: Setup, plugin: Callable[..., Plugin]) -> Plugin:
    """Turn the tracker on and give Alice an Assistant of a plugin that knows tasks.

    Args:
        setup: The Team.
        plugin: Factory of plugin installations.
    """
    setup.alice.patch(f"/api/team/{setup.team}", json={"tracker": True})
    return plugin(setup.alice, "billing-api", setup.team, session="b1", version=NEW)


def _plan(setup: Setup, title: str, **more: object) -> int:
    """Put a task in the backlog in the web; return its number.

    Args:
        setup: The Team.
        title: Its title.
        **more: More fields.
    """
    created = setup.alice.post(
        f"/api/team/{setup.team}/task", json={"area": setup.area, "title": title, **more}
    )
    assert created.status_code == 201, created.text
    return created.json()["number"]


def _board(setup: Setup, **query: object) -> dict:
    """Return the board.

    Args:
        setup: The Team.
        **query: Filters.
    """
    response = setup.alice.get(f"/api/team/{setup.team}/board", params=query)
    assert response.status_code == 200, response.text
    return response.json()


def _where(board: dict) -> dict[int, str]:
    """Return each card's column name by task number.

    Args:
        board: The board.
    """
    return {card["number"]: board["columns"][card["column"]]["name"] for card in board["cards"]}


def test_the_built_in_board_groups_stages_by_category(setup: Setup, alice: Plugin) -> None:
    """To do, In progress, Done; tasks by stage; promises and old finished tasks are not on it.

    Args:
        setup: The Team.
        alice: Alice's Assistant.
    """
    backlog = _plan(setup, "Later")
    working = alice.client.post(
        f"/api/team/{setup.team}/topic", json={"area": setup.area, "title": "Now", "body": "Hi"}
    ).json()["number"]
    done = alice.client.post(
        f"/api/team/{setup.team}/topic", json={"area": setup.area, "title": "Old", "body": "Hi"}
    ).json()["number"]
    alice.client.post(f"/api/team/{setup.team}/task/{done}/close", json={"outcome": "ok"})
    _plan(setup, "A promise", type="promise")

    board = _board(setup)

    assert [(c["name"], c["rule"]) for c in board["columns"]] == [
        ("To do", "stages"),
        ("In progress", "stages"),
        ("Done", "stages"),
    ]
    assert board["columns"][0]["stages"] == ["Backlog"]
    assert board["columns"][2]["stages"] == ["Done", "Cancelled"]
    assert _where(board) == {backlog: "To do", working: "In progress", done: "Done"}


def test_a_finished_task_leaves_the_board_after_two_weeks(
    setup: Setup, alice: Plugin, settings: Settings
) -> None:
    """Done shows the last two weeks; the rest are in the list (decision 0032).

    Args:
        setup: The Team.
        alice: Alice's Assistant.
        settings: Instance settings.
    """
    number = alice.client.post(
        f"/api/team/{setup.team}/topic", json={"area": setup.area, "title": "Old", "body": "Hi"}
    ).json()["number"]
    alice.client.post(f"/api/team/{setup.team}/task/{number}/close", json={"outcome": "ok"})
    with _connect(settings.database_url) as connection:
        connection.execute(
            "UPDATE tasks SET finished_at = %s WHERE number = %s",
            (now() - timedelta(days=15), number),
        )

    assert _board(setup)["cards"] == []


def test_a_waiting_task_stands_in_the_waiting_column(setup: Setup, alice: Plugin) -> None:
    """A waiting column shows the tasks with an active external wait, whatever their stage, and
    the card says what is awaited.

    Args:
        setup: The Team.
        alice: Alice's Assistant.
    """
    number = alice.client.post(
        f"/api/team/{setup.team}/topic", json={"area": setup.area, "title": "Now", "body": "Hi"}
    ).json()["number"]
    columns = [
        {"name": "To do", "stages": ["Backlog"]},
        {"name": "Working", "stages": ["Analysis", "Design", "Documentation", "Agreement", "Code"]},
        {"name": "Waiting", "rule": "waiting"},
        {"name": "Review", "stages": ["Review", "Delivery"]},
        {"name": "Done", "stages": ["Done", "Cancelled"]},
    ]
    saved = setup.alice.put(f"/api/team/{setup.team}/board", json={"columns": columns})
    alice.client.post(f"/api/team/{setup.team}/task/{number}/wait", json={"what": "a token"})
    waiting = _board(setup)
    alice.client.post(f"/api/team/{setup.team}/task/{number}/resume")

    assert saved.status_code == 200, saved.text
    assert _where(waiting) == {number: "Waiting"}
    (card,) = waiting["cards"]
    assert (card["stage"], card["move"], card["move_who"]) == ("Analysis", "external", "a token")
    assert _where(_board(setup)) == {number: "Working"}


@pytest.mark.parametrize(
    ("columns", "says"),
    [
        ([{"name": "All", "stages": ["Backlog", "Analysis"]}], "not shown"),
        (
            [
                {"name": "A", "stages": ["Backlog", "Analysis", "Design", "Documentation"]},
                {
                    "name": "B",
                    "stages": ["Backlog", "Agreement", "Code", "Review", "Delivery", "Done"],
                },
            ],
            "shown twice",
        ),
        ([{"name": "W", "rule": "waiting", "stages": ["Backlog"]}], "not by stages"),
        ([{"name": "X", "stages": ["Testing"]}], "No stage"),
    ],
)
def test_every_stage_stands_in_one_column(
    setup: Setup, alice: Plugin, columns: list, says: str
) -> None:
    """The owner cannot leave a stage out, show it twice, or give stages to the waiting column.

    Args:
        setup: The Team.
        alice: Alice's Assistant.
        columns: The columns tried.
        says: What the refusal says.
    """
    refused = setup.alice.put(f"/api/team/{setup.team}/board", json={"columns": columns})
    by_member = setup.bob.put(f"/api/team/{setup.team}/board", json={"columns": columns})

    assert refused.status_code == 422 and says in refused.json()["detail"]
    assert by_member.status_code == 403


def test_the_owner_edits_the_workflow(setup: Setup, alice: Plugin) -> None:
    """Renaming, reordering, adding and removing stages; a removed stage's tasks move with a
    timeline entry; a new stage joins the column of its category; kinds stay.

    Args:
        setup: The Team.
        alice: Alice's Assistant.
    """
    number = alice.client.post(
        f"/api/team/{setup.team}/topic", json={"area": setup.area, "title": "Now", "body": "Hi"}
    ).json()["number"]
    alice.client.post(f"/api/team/{setup.team}/task/{number}/stage", json={"stage": "Design"})
    stages = [
        {"name": "Backlog", "kind": "backlog", "was": "Backlog"},
        {"name": "Анализ", "kind": "analysis", "was": "Analysis"},
        {"name": "Code", "kind": "code", "was": "Code"},
        {"name": "QA", "kind": "review"},
        {"name": "Done", "kind": "done", "was": "Done"},
    ]
    path = f"/api/team/{setup.team}/workflow/task"

    no_move = setup.alice.put(path, json={"stages": stages})
    kind_changed = setup.alice.put(
        path,
        json={"stages": [{"name": "Backlog", "kind": "analysis", "was": "Backlog"}, *stages[1:]]},
    )
    no_done = setup.alice.put(path, json={"stages": stages[:-1], "moves": {"Design": "Code"}})
    to_finished = setup.alice.put(path, json={"stages": stages, "moves": {"Design": "Done"}})
    by_member = setup.bob.put(path, json={"stages": stages, "moves": {"Design": "Code"}})
    saved = setup.alice.put(path, json={"stages": stages, "moves": {"Design": "Code"}})
    task = setup.alice.get(f"/api/team/{setup.team}/task/{number}").json()
    board = _board(setup)

    assert "name the stage to move them to" in no_move.json()["detail"]
    assert "keeps its kind" in kind_changed.json()["detail"]
    assert "needs done" in no_done.json()["detail"]
    assert "same category" in to_finished.json()["detail"]
    assert by_member.status_code == 403
    assert saved.json() == ["Backlog", "Анализ", "Code", "QA", "Done"]
    assert task["stage"] == "Code"
    last = task["timeline"][-1]
    assert (last["kind"], last["data"]["from"], last["data"]["workflow"]) == (
        "stage",
        "Design",
        True,
    )
    assert board["columns"][1]["stages"] == ["Анализ", "Code", "QA"]


def test_work_starts_in_the_backlog_without_stages_of_work(setup: Setup, alice: Plugin) -> None:
    """A Team that kept only the backlog and done starts new work in the backlog.

    Args:
        setup: The Team.
        alice: Alice's Assistant.
    """
    setup.alice.put(
        f"/api/team/{setup.team}/workflow/task",
        json={
            "stages": [
                {"name": "Backlog", "kind": "backlog", "was": "Backlog"},
                {"name": "Done", "kind": "done", "was": "Done"},
            ]
        },
    )

    opened = alice.client.post(
        f"/api/team/{setup.team}/topic", json={"area": setup.area, "title": "Now", "body": "Hi"}
    )

    assert opened.status_code == 201, opened.text
    assert opened.json()["stage"] == "Backlog"


def test_the_board_filters_by_area_person_and_promise(setup: Setup, alice: Plugin) -> None:
    """Filters by Area, assignee and promise; a goal's filter takes all below it.

    Args:
        setup: The Team.
        alice: Alice's Assistant.
    """
    setup.alice.post(f"/api/team/{setup.team}/area", json={"name": "Design"})
    goal = _plan(setup, "Billing by December", type="promise")
    promise = _plan(setup, "Invoices", type="promise", parent=goal)
    inside = _plan(setup, "API", parent=promise, assignee="bob")
    sub = _plan(setup, "Schema", parent=inside)
    outside = _plan(setup, "Other", area="design")

    by_goal = _board(setup, promise=goal)
    by_person = _board(setup, assignee="bob")
    by_area = _board(setup, area="design")
    cards = {c["number"]: c for c in _board(setup)["cards"]}

    assert sorted(c["number"] for c in by_goal["cards"]) == [inside, sub]
    assert [c["number"] for c in by_person["cards"]] == [inside]
    assert [c["number"] for c in by_area["cards"]] == [outside]
    assert cards[sub]["promise"] == {"number": promise, "title": "Invoices"}


def test_a_card_tells_whose_move_it_is(setup: Setup, alice: Plugin) -> None:
    """A question to another person makes the move theirs until they answer; then the holding
    session's last interval tells (decision 0033).

    Args:
        setup: The Team.
        alice: Alice's Assistant.
    """
    number = alice.client.post(
        f"/api/team/{setup.team}/topic", json={"area": setup.area, "title": "Now", "body": "Hi"}
    ).json()["number"]
    path = f"/api/team/{setup.team}/task/{number}"
    start = now() - timedelta(minutes=10)
    alice.client.post(
        "/api/moves",
        json={
            "intervals": [
                {
                    "move": "assistant",
                    "start": start.isoformat(),
                    "end": (start + timedelta(minutes=5)).isoformat(),
                }
            ]
        },
    )
    humans = _board(setup)["cards"][0]
    alice.client.post(f"{path}/message", json={"number": 2, "body": "Bob?", "to": "bob"})
    asked = _board(setup)["cards"][0]
    setup.bob.post(f"{path}/message", json={"number": 3, "body": "Yes"})
    answered = _board(setup)["cards"][0]

    assert (humans["move"], humans["move_who"]) == ("human", "alice")
    assert (asked["move"], asked["move_who"]) == ("person", "bob")
    assert answered["move"] == "human"


def test_a_promise_has_a_period_progress_and_three_endings(setup: Setup, alice: Plugin) -> None:
    """A promise carries its period, counts what it holds, and ends delivered, not delivered or
    withdrawn (decisions 0031, 0032).

    Args:
        setup: The Team.
        alice: Alice's Assistant.
    """
    promise = _plan(
        setup, "Reports", type="promise", period_start="2026-11-01", period_end="2026-11-30"
    )
    tasks = [_plan(setup, f"Task {n}", parent=promise, assignee="alice") for n in range(3)]
    for number in tasks:
        alice.client.post(f"/api/team/{setup.team}/task/{number}/take", json={})
    alice.client.post(f"/api/team/{setup.team}/task/{tasks[0]}/close", json={"outcome": "ok"})
    alice.client.post(
        f"/api/team/{setup.team}/task/{tasks[1]}/close", json={"outcome": "no", "cancelled": True}
    )
    alice.client.post(f"/api/team/{setup.team}/task/{promise}/take", json={})
    moved = setup.alice.patch(
        f"/api/team/{setup.team}/task/{promise}", json={"period_end": "2026-12-05"}
    ).json()
    missed = alice.client.post(
        f"/api/team/{setup.team}/task/{promise}/close",
        json={"outcome": "API not ready", "missed": True},
    ).json()
    detail = setup.alice.get(f"/api/team/{setup.team}/task/{promise}").json()

    assert (moved["period_start"], moved["period_end"]) == ("2026-11-01", "2026-12-05")
    assert moved["progress"] == {"done": 1, "total": 2}
    assert (missed["stage"], missed["stage_kind"]) == ("Not delivered", "not_delivered")
    assert "period" in [e["kind"] for e in detail["timeline"]]


def test_two_first_readers_build_one_board(setup: Setup, alice: Plugin, settings: Settings) -> None:
    """Two people opening a board for the first time together get the same one (decision 0032).

    Args:
        setup: The Team.
        alice: Alice's Assistant.
        settings: Instance settings.
    """
    import asyncio

    from coloqo_server.api.boards import main_board
    from coloqo_server.db import Database

    with _connect(settings.database_url) as connection:
        ((team_id,),) = connection.execute(
            "SELECT id FROM teams WHERE slug = %s", (setup.team,)
        ).fetchall()

    async def read() -> int:
        """Build or find the board in a session of its own, holding it a moment."""
        database = Database(settings.database_url)
        try:
            async with database.sessions() as db:
                board = await main_board(db, team_id)
                await asyncio.sleep(0.2)
                await db.commit()
                return board.id
        finally:
            await database.dispose()

    async def both() -> list[int]:
        """Read twice at once."""
        return list(await asyncio.gather(read(), read()))

    first, second = asyncio.run(both())
    with _connect(settings.database_url) as connection:
        ((boards,),) = connection.execute(
            "SELECT count(*) FROM boards WHERE team_id = %s", (team_id,)
        ).fetchall()

    assert first == second
    assert boards == 1
