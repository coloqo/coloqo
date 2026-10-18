"""Tests of the ``coloqo`` command."""

import subprocess
import sys

import pytest

from coloqo import __version__
from coloqo.cli import main


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    """``--version`` prints the installed version and exits with 0.

    Args:
        capsys: Captured output from pytest.
    """
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"coloqo {__version__}\n"


def test_no_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Without arguments the command prints its help.

    Args:
        capsys: Captured output from pytest.
    """
    assert main([]) == 0
    assert capsys.readouterr().out.startswith("usage: coloqo")


def test_unknown_argument_fails() -> None:
    """An unknown argument is a usage error, exit code 2."""
    with pytest.raises(SystemExit) as exit_info:
        main(["--no-such-option"])

    assert exit_info.value.code == 2


def test_module_entry_point() -> None:
    """``python -m coloqo --version`` works like the installed script."""
    result = subprocess.run(
        [sys.executable, "-m", "coloqo", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == f"coloqo {__version__}\n"
