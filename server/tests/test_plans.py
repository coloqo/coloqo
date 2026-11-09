"""Tests of plans: drafts, approval, marks, rows, postponing, closing (decision 0037)."""

from collections.abc import Callable
from datetime import date, timedelta

import pytest

from coloqo_server.settings import Settings
from tests.conftest import Plugin, Setup, _connect

NEW = "0.11.0"
"""A plugin release that knows tasks and deliveries."""

TODAY = date.today()


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
    for number in (started["number"], done["number"]):
        alice_new.client.post(f"/api/team/{setup.team}/task/{number}/take", json={"body": "On it"})
    alice_new.client.post(
        f"/api/team/{setup.team}/task/{done['number']}/close", json={"outcome": "Merged"}
    )
    running = _plan(setup.alice, setup, TODAY - timedelta(days=2), TODAY + timedelta(days=20))
    coming = _plan(
        setup.alice, setup, TODAY + timedelta(days=30), TODAY + timedelta(days=60), "Next"
    )
    every = [idle["number"], started["number"], done["number"]]
    setup.alice.post(_url(setup, running, "/item"), json={"tasks": every})
    setup.alice.post(_url(setup, coming, "/item"), json={"tasks": [started["number"]]})

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
    for number in (shipped["number"], dropped["number"]):
        alice_new.client.post(f"/api/team/{setup.team}/task/{number}/take", json={"body": "On it"})
    alice_new.client.post(
        f"/api/team/{setup.team}/task/{shipped['number']}/close", json={"outcome": "Merged"}
    )
    alice_new.client.post(
        f"/api/team/{setup.team}/task/{dropped['number']}/close",
        json={"outcome": "Not needed", "cancelled": True},
    )
    current = _plan(setup.alice, setup, TODAY, TODAY + timedelta(days=20), "Now")
    every = [shipped["number"], dropped["number"], left["number"]]
    setup.alice.post(_url(setup, current, "/item"), json={"tasks": every})
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
    }
    assert (closed["summary"]["planned"], closed["summary"]["planned_done"]) == (3, 1)
    assert offered == [left["number"]]
    assert _rows(taken)[left["number"]]["carried_from"] == "Now"
