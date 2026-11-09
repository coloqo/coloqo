"""Tests of plans: drafts, approval, marks, rows, postponing, closing (decision 0037)."""

import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest

from coloqo_server.settings import Settings
from tests.conftest import Plugin, Setup, _connect

NEW = "0.11.0"
"""A plugin release that knows tasks and deliveries."""

TODAY = datetime.now(UTC).date()
"""Today in a test Team, which counts its days in UTC unless a test sets its time zone."""


@pytest.fixture
def alice_new(setup: Setup, plugin: Callable[..., Plugin]) -> Plugin:
    """Give Alice an Assistant of a plugin that knows tasks, with the tracker on.

    Args:
        setup: The Team.
        plugin: Factory of plugin installations.
    """
    response = setup.alice.patch(f"/api/team/{setup.team}", json={"tracker": True})
    assert response.json()["tracker"] is True
    return plugin(setup.alice, "billing-api", setup.team, session="p1", version=NEW)


def _task(setup: Setup, title: str, kind: str = "task", parent: int | None = None, **more) -> dict:
    """Create a task in the backlog by Alice in the web.

    Args:
        setup: The Team.
        title: Its title.
        kind: ``task`` or ``promise``.
        parent: Its parent's number.
        **more: Other fields.
    """
    response = setup.alice.post(
        f"/api/team/{setup.team}/task",
        json={"area": setup.area, "title": title, "type": kind, "parent": parent, **more},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _plan(client, setup: Setup, start: date, end: date, name: str = "November") -> dict:
    """Create a plan.

    Args:
        client: Who creates it.
        setup: The Team.
        start: Its first day.
        end: Its last day.
        name: Its name.
    """
    response = client.post(
        f"/api/team/{setup.team}/plan",
        json={"name": name, "period_start": start.isoformat(), "period_end": end.isoformat()},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _url(setup: Setup, plan: dict, rest: str = "") -> str:
    """Return a plan's address in the API.

    Args:
        setup: The Team.
        plan: The plan.
        rest: A path under it.
    """
    return f"/api/team/{setup.team}/plan/{plan['number']}{rest}"


def _rows(plan: dict) -> dict[int, dict]:
    """Return a plan's rows by task number.

    Args:
        plan: The plan's detail.
    """
    return {row["task"]["number"]: row for row in plan["items"]}


def test_an_assistant_drafts_a_plan_and_a_human_approves(setup: Setup, alice_new: Plugin) -> None:
    """An Assistant creates a plan and fills its draft; a promise brings its unfinished tasks;
    plans do not overlap; approving is a human's (decision 0037).

    Args:
        setup: The Team.
        alice_new: Alice's Assistant.
    """
    promise = _task(setup, "Invoices", "promise")
    first = _task(setup, "API", parent=promise["number"])
    second = _task(setup, "PDF", parent=promise["number"])
    loose = _task(setup, "Onboarding")
    plan = _plan(alice_new.client, setup, TODAY, TODAY + timedelta(days=20))

    added = alice_new.client.post(
        _url(setup, plan, "/item"), json={"tasks": [promise["number"], loose["number"]]}
    ).json()
    overlap = alice_new.client.post(
        f"/api/team/{setup.team}/plan",
        json={
            "name": "Dup",
            "period_start": (TODAY + timedelta(days=5)).isoformat(),
            "period_end": (TODAY + timedelta(days=40)).isoformat(),
        },
    )
    by_assistant = alice_new.client.post(_url(setup, plan, "/approve"))
    approved = setup.alice.post(_url(setup, plan, "/approve")).json()
    late_by_assistant = alice_new.client.post(
        _url(setup, plan, "/item"), json={"tasks": [loose["number"]]}
    )
    timeline = setup.alice.get(f"/api/team/{setup.team}/task/{first['number']}").json()["timeline"]

    rows = _rows(added)
    assert set(rows) == {promise["number"], first["number"], second["number"], loose["number"]}
    assert {row["mark"] for row in rows.values()} == {"planned"}
    assert added["state"] == "draft"
    assert overlap.json()["detail"]["code"] == "overlap"
    assert by_assistant.status_code == 403
    assert (approved["state"], approved["approved_by"]) == ("approved", "alice")
    assert late_by_assistant.status_code == 403
    assert "plan_joined" in [e["kind"] for e in timeline]


def test_work_joining_after_approval_is_found_or_off_plan(setup: Setup, alice_new: Plugin) -> None:
    """After approval a task created under planned work joins by itself: found only by a source
    its creator named; a source filled in from the held Topic leaves it off-plan (0037).

    Args:
        setup: The Team.
        alice_new: Alice's Assistant.
    """
    promise = _task(setup, "Invoices", "promise")
    planned = _task(setup, "API", parent=promise["number"])
    plan = _plan(setup.alice, setup, TODAY, TODAY + timedelta(days=20))
    setup.alice.post(_url(setup, plan, "/item"), json={"tasks": [promise["number"]]})
    setup.alice.post(_url(setup, plan, "/approve"))
    # Alice's Assistant takes the planned task: it now holds its Topic.
    alice_new.client.post(
        f"/api/team/{setup.team}/task/{planned['number']}/take", json={"body": "Taking it"}
    )

    def create(title: str, **more) -> int:
        """Create a task under the promise by Alice's Assistant.

        Args:
            title: Its title.
            **more: Other fields.
        """
        response = alice_new.client.post(
            f"/api/team/{setup.team}/task",
            json={"area": setup.area, "title": title, "parent": promise["number"], **more},
        )
        assert response.status_code == 201, response.text
        return response.json()["number"]

    found = create("Found while doing the API", source=planned["number"])
    implicit = create("Urgent and unrelated")
    rows = _rows(setup.alice.get(_url(setup, plan)).json())
    implicit_task = setup.alice.get(f"/api/team/{setup.team}/task/{implicit}").json()

    assert rows[found]["mark"] == "found"
    assert rows[implicit]["mark"] == "off_plan"
    assert implicit_task["source"] == planned["number"]


def test_a_human_shapes_the_rows(setup: Setup, alice_new: Plugin) -> None:
    """A human corrects found ↔ off-plan, names what off-plan work drops and postpones a row
    with a reason; an Assistant does none of it (decision 0037).

    Args:
        setup: The Team.
        alice_new: Alice's Assistant.
    """
    promise = _task(setup, "Invoices", "promise")
    planned = _task(setup, "API", parent=promise["number"])
    plan = _plan(setup.alice, setup, TODAY, TODAY + timedelta(days=20))
    setup.alice.post(_url(setup, plan, "/item"), json={"tasks": [promise["number"]]})
    setup.alice.post(_url(setup, plan, "/approve"))
    urgent = _task(setup, "Hotfix", parent=promise["number"])
    row = _url(setup, plan, f"/item/{urgent['number']}")
    planned_row = _url(setup, plan, f"/item/{planned['number']}")

    unnamed = setup.alice.get(_url(setup, plan)).json()["summary"]["dropped_unnamed"]
    by_assistant = alice_new.client.patch(row, json={"dropped": f"T-{planned['number']}"})
    named = setup.alice.patch(row, json={"dropped": f"T-{planned['number']} is put off"}).json()
    corrected = setup.alice.patch(row, json={"mark": "found"}).json()
    planned_mark = setup.alice.patch(planned_row, json={"mark": "off_plan"})
    no_reason = setup.alice.patch(planned_row, json={"postponed": True})
    postponed = setup.alice.patch(
        planned_row, json={"postponed": True, "reason": f"in favour of T-{urgent['number']}"}
    ).json()
    resumed = setup.alice.patch(planned_row, json={"postponed": False}).json()
    kinds = [
        e["kind"]
        for e in setup.alice.get(f"/api/team/{setup.team}/task/{planned['number']}").json()[
            "timeline"
        ]
    ]

    assert unnamed == 1
    assert by_assistant.status_code == 403
    assert _rows(named)[urgent["number"]]["dropped"] == f"T-{planned['number']} is put off"
    assert named["summary"]["dropped_unnamed"] == 0
    assert _rows(corrected)[urgent["number"]]["mark"] == "found"
    assert planned_mark.status_code == 422
    assert no_reason.status_code == 422
    assert _rows(postponed)[planned["number"]]["postponed"] is True
    assert postponed["summary"]["postponed"] == 1
    assert _rows(resumed)[planned["number"]]["postponed"] is False
    assert {"plan_postponed", "plan_resumed"} <= set(kinds)


def test_what_leaves_a_draft(setup: Setup, alice_new: Plugin) -> None:
    """A task leaves a draft when not started; a started one only before the period; a finished
    one never; an approved plan keeps its rows (decision 0037).

    Args:
        setup: The Team.
        alice_new: Alice's Assistant.
    """
    idle = _task(setup, "Idle")
    started = _task(setup, "Started")
    done = _task(setup, "Done")
    running = _plan(setup.alice, setup, TODAY - timedelta(days=2), TODAY + timedelta(days=20))
    coming = _plan(
        setup.alice, setup, TODAY + timedelta(days=30), TODAY + timedelta(days=60), "Next"
    )
    every = [idle["number"], started["number"], done["number"]]
    setup.alice.post(_url(setup, running, "/item"), json={"tasks": every})
    setup.alice.post(_url(setup, coming, "/item"), json={"tasks": [started["number"]]})
    for number in (started["number"], done["number"]):
        alice_new.client.post(f"/api/team/{setup.team}/task/{number}/take", json={"body": "On it"})
    alice_new.client.post(
        f"/api/team/{setup.team}/task/{done['number']}/close", json={"outcome": "Merged"}
    )

    def remove(plan: dict, number: int):
        """Try to take a task out of a plan.

        Args:
            plan: The plan.
            number: The task.
        """
        return alice_new.client.delete(_url(setup, plan, f"/item/{number}"))

    idle_out = remove(running, idle["number"])
    started_in_period = remove(running, started["number"])
    finished = remove(running, done["number"])
    started_before_period = remove(coming, started["number"])
    setup.alice.post(_url(setup, running, "/approve"))
    approved = remove(running, started["number"])

    assert idle_out.status_code == 200, idle_out.text
    assert started_in_period.json()["detail"]["code"] == "started"
    assert finished.json()["detail"]["code"] == "finished"
    assert started_before_period.status_code == 200, started_before_period.text
    assert approved.json()["detail"]["code"] == "not_draft"


def test_closing_fixes_the_month_and_the_next_draft_carries_it(
    setup: Setup, alice_new: Plugin, settings: Settings
) -> None:
    """Closing after the period fixes each row's result; the next plan shows what came from it
    and its draft offers what was not done (decision 0037).

    Args:
        setup: The Team.
        alice_new: Alice's Assistant.
        settings: Instance settings.
    """
    shipped = _task(setup, "Shipped")
    dropped = _task(setup, "Dropped")
    left = _task(setup, "Left")
    late = _task(setup, "Finished after the month")
    current = _plan(setup.alice, setup, TODAY, TODAY + timedelta(days=20), "Now")
    every = [shipped["number"], dropped["number"], left["number"], late["number"]]
    setup.alice.post(_url(setup, current, "/item"), json={"tasks": every})
    for number in (shipped["number"], dropped["number"]):
        alice_new.client.post(f"/api/team/{setup.team}/task/{number}/take", json={"body": "On it"})
    alice_new.client.post(
        f"/api/team/{setup.team}/task/{shipped['number']}/close", json={"outcome": "Merged"}
    )
    alice_new.client.post(
        f"/api/team/{setup.team}/task/{dropped['number']}/close",
        json={"outcome": "Not needed", "cancelled": True},
    )
    setup.alice.post(_url(setup, current, "/approve"))
    early = setup.alice.post(_url(setup, current, "/close"))
    # The month is over: move the plan into the past, the shipped task finished within it.
    with _connect(settings.database_url) as connection:
        connection.execute(
            "UPDATE plans SET period_start = %s, period_end = %s WHERE number = %s",
            (TODAY - timedelta(days=40), TODAY - timedelta(days=10), current["number"]),
        )
        connection.execute(
            "UPDATE tasks SET finished_at = finished_at - interval '20 days' WHERE number = %s "
            "AND team_id = (SELECT id FROM teams WHERE slug = %s)",
            (shipped["number"], setup.team),
        )
    by_assistant = alice_new.client.post(_url(setup, current, "/close"))
    closed = setup.alice.post(_url(setup, current, "/close")).json()
    # Left undone in the closed month, finished today: within the next plan's period.
    alice_new.client.post(f"/api/team/{setup.team}/task/{late['number']}/take", json={"body": "On"})
    alice_new.client.post(
        f"/api/team/{setup.team}/task/{late['number']}/close", json={"outcome": "Merged later"}
    )
    following = _plan(alice_new.client, setup, TODAY, TODAY + timedelta(days=20), "Next")
    offered = following["previous_unfinished"]
    taken = alice_new.client.post(_url(setup, following, "/item"), json={"tasks": offered}).json()

    results = {n: row["result"] for n, row in _rows(closed).items()}
    assert early.json()["detail"]["code"] == "period"
    assert by_assistant.status_code == 403
    assert results == {
        shipped["number"]: "done",
        dropped["number"]: "cancelled",
        left["number"]: "not_done",
        late["number"]: "not_done",
    }
    assert (closed["summary"]["planned"], closed["summary"]["planned_done"]) == (4, 1)
    assert offered == [left["number"], late["number"]]
    assert _rows(taken)[left["number"]]["carried_from"] == "Now"


def test_work_finished_before_the_period_stays_out(
    setup: Setup, alice_new: Plugin, settings: Settings
) -> None:
    """Work finished before the plan's period is refused by number, is not brought by its
    promise and does not join when moved under planned work; work finished within the period
    joins (the author, 2026-11-10; decision 0037).

    Args:
        setup: The Team.
        alice_new: Alice's Assistant.
        settings: Instance settings.
    """
    promise = _task(setup, "Invoices", "promise")
    old = _task(setup, "Shipped in October")
    under = _task(setup, "Shipped in October too", parent=promise["number"])
    recent = _task(setup, "Shipped this month", parent=promise["number"])
    loose = _task(setup, "Also shipped this month")
    for task in (old, under, recent, loose):
        number = task["number"]
        alice_new.client.post(f"/api/team/{setup.team}/task/{number}/take", json={"body": "On it"})
        alice_new.client.post(f"/api/team/{setup.team}/task/{number}/close", json={"outcome": "Ok"})
    with _connect(settings.database_url) as connection:
        connection.execute(
            "UPDATE tasks SET finished_at = finished_at - interval '30 days' "
            "WHERE number = ANY(%s) AND team_id = (SELECT id FROM teams WHERE slug = %s)",
            ([old["number"], under["number"]], setup.team),
        )
    plan = _plan(setup.alice, setup, TODAY - timedelta(days=5), TODAY + timedelta(days=20))
    setup.alice.post(_url(setup, plan, "/item"), json={"tasks": [promise["number"]]})

    by_number = setup.alice.post(_url(setup, plan, "/item"), json={"tasks": [old["number"]]})
    within = setup.alice.post(_url(setup, plan, "/item"), json={"tasks": [loose["number"]]})
    setup.alice.patch(
        f"/api/team/{setup.team}/task/{old['number']}", json={"parent": promise["number"]}
    )
    rows = _rows(setup.alice.get(_url(setup, plan)).json())

    assert by_number.json()["detail"]["code"] == "finished"
    assert old["number"] not in rows
    assert under["number"] not in rows
    assert rows[recent["number"]]["mark"] == "planned"
    assert within.status_code == 200, within.text
    assert rows[loose["number"]]["mark"] == "planned"


def test_a_row_joined_twice_at_once_is_found_there(
    setup: Setup, alice_new: Plugin, settings: Settings
) -> None:
    """A move under planned work that meets a row another writer is inserting finds the row
    there instead of failing (decision 0037).

    Args:
        setup: The Team.
        alice_new: Alice's Assistant.
        settings: Instance settings.
    """
    promise = _task(setup, "Invoices", "promise")
    loose = _task(setup, "Loose")
    plan = _plan(setup.alice, setup, TODAY, TODAY + timedelta(days=20))
    setup.alice.post(_url(setup, plan, "/item"), json={"tasks": [promise["number"]]})
    answer: list = []
    with _connect(settings.database_url) as other:
        other.execute("BEGIN")
        other.execute(
            "INSERT INTO plan_items (plan_id, task_id, mark) VALUES ("
            "(SELECT id FROM plans WHERE number = %s), "
            "(SELECT id FROM tasks WHERE number = %s AND team_id = "
            "(SELECT id FROM teams WHERE slug = %s)), 'planned')",
            (plan["number"], loose["number"], setup.team),
        )
        mover = threading.Thread(
            target=lambda: answer.append(
                setup.alice.patch(
                    f"/api/team/{setup.team}/task/{loose['number']}",
                    json={"parent": promise["number"]},
                )
            )
        )
        mover.start()
        mover.join(1)
        other.execute("COMMIT")
    mover.join(30)

    assert answer[0].status_code == 200, answer[0].text
    assert loose["number"] in _rows(setup.alice.get(_url(setup, plan)).json())


def test_a_plan_counts_days_in_its_team_s_time_zone(
    setup: Setup, alice_new: Plugin, settings: Settings
) -> None:
    """A Team's time zone sets its plans' days: a task finished at 20:00 UTC the evening before
    the period is finished on its first day in Tokyo, so it joins (decision 0037). Only the owner
    sets the zone, and only a zone the server knows.

    Args:
        setup: The Team.
        alice_new: Alice's Assistant.
        settings: Instance settings.
    """
    start = TODAY + timedelta(days=3)
    task = _task(setup, "Shipped at dawn in Tokyo")
    alice_new.client.post(f"/api/team/{setup.team}/task/{task['number']}/take", json={"body": "On"})
    alice_new.client.post(
        f"/api/team/{setup.team}/task/{task['number']}/close", json={"outcome": "Ok"}
    )
    evening = datetime.combine(start - timedelta(days=1), datetime.min.time(), UTC) + timedelta(
        hours=20
    )
    with _connect(settings.database_url) as connection:
        connection.execute(
            "UPDATE tasks SET finished_at = %s WHERE number = %s "
            "AND team_id = (SELECT id FROM teams WHERE slug = %s)",
            (evening, task["number"], setup.team),
        )
    plan = _plan(setup.alice, setup, start, start + timedelta(days=20))

    in_utc = setup.alice.post(_url(setup, plan, "/item"), json={"tasks": [task["number"]]})
    by_member = setup.bob.patch(f"/api/team/{setup.team}", json={"time_zone": "Asia/Tokyo"})
    unknown = setup.alice.patch(f"/api/team/{setup.team}", json={"time_zone": "Mars/Olympus"})
    zoned = setup.alice.patch(f"/api/team/{setup.team}", json={"time_zone": "Asia/Tokyo"}).json()
    in_tokyo = setup.alice.post(_url(setup, plan, "/item"), json={"tasks": [task["number"]]})

    assert in_utc.json()["detail"]["code"] == "finished"
    assert by_member.status_code == 403
    assert unknown.status_code == 422
    assert zoned["time_zone"] == "Asia/Tokyo"
    assert in_tokyo.status_code == 200, in_tokyo.text
    assert task["number"] in _rows(in_tokyo.json())


def test_a_new_team_takes_the_zone_it_is_given(setup: Setup) -> None:
    """The web sends its creator's browser's zone; without one a Team starts in UTC (0037).

    Args:
        setup: The Team.
    """
    given = setup.alice.post("/api/team", json={"name": "Zoned", "time_zone": "Europe/Moscow"})
    plain = setup.alice.post("/api/team", json={"name": "Plain"})

    assert given.json()["time_zone"] == "Europe/Moscow"
    assert plain.json()["time_zone"] == "UTC"
