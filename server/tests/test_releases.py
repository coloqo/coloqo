"""Test of learning the plugin's latest release from PyPI (decision 0027)."""

import asyncio

import httpx
import pytest

from coloqo_server import releases


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (httpx.Response(200, json={"info": {"version": "0.5.1"}}), (0, 5, 1)),
        (httpx.Response(200, json={"info": {"version": "0.6.0rc1"}}), None),
        (httpx.Response(200, json={"releases": {}}), None),
        (httpx.Response(503), None),
    ],
)
def test_latest_release_or_none(
    monkeypatch: pytest.MonkeyPatch, answer: httpx.Response, expected: tuple[int, ...] | None
) -> None:
    """The version PyPI names is read; anything else leaves it unknown.

    Args:
        monkeypatch: Patching helper from pytest.
        answer: What PyPI answers.
        expected: The version learned.
    """
    real = httpx.AsyncClient

    def client(**kwargs: object) -> httpx.AsyncClient:
        """Make a client that gets the given answer.

        Args:
            **kwargs: What the code passes.
        """
        return real(transport=httpx.MockTransport(lambda request: answer))

    monkeypatch.setattr(releases.httpx, "AsyncClient", client)

    assert asyncio.run(releases.latest_release("https://pypi.example/coloqo/json")) == expected
