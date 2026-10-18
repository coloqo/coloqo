"""The ``coloqo`` command."""

import argparse

from coloqo import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the parser of the ``coloqo`` command.

    The subcommands ``mcp``, ``hook``, ``watch`` and ``login`` (decision 0011) join it as they
    are built.
    """
    parser = argparse.ArgumentParser(
        prog="coloqo",
        description="Connect an AI agent to Coloqo, where a team's assistants work together.",
        epilog="Early stage: https://github.com/coloqo/coloqo",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command.

    Without arguments it prints the help.

    Args:
        argv: Command-line arguments without the program name; ``sys.argv[1:]`` when omitted.

    Raises:
        SystemExit: On ``--version`` and ``--help`` (exit code 0) and on an unknown argument
            (exit code 2), raised by ``argparse``.
    """
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
