"""Module entrypoint so ``python -m issuesuite`` invokes the CLI.

``run()`` simply calls :func:`issuesuite.cli.main` allowing argparse to
consume the real command line arguments when executed as a module.
"""

from __future__ import annotations

from .cli import main


def run() -> int:  # pragma: no cover - thin wrapper
    return main(None)


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(run())
