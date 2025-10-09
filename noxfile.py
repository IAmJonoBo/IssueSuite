from __future__ import annotations

from pathlib import Path

import nox

nox.options.default_venv_backend = "virtualenv"
nox.options.error_on_missing_interpreters = False

DOCS_DIR = Path("docs/starlight")


def _install_tools(session: nox.Session) -> None:
    session.install("-e", ".[dev]")


@nox.session
def tests(session: nox.Session) -> None:
    _install_tools(session)
    session.run("pytest", "--cov=issuesuite", "--cov-report=term", "--cov-report=xml")


@nox.session
def lint(session: nox.Session) -> None:
    _install_tools(session)
    session.run("ruff", "check")


@nox.session
def typecheck(session: nox.Session) -> None:
    _install_tools(session)
    session.run("mypy", "src")


@nox.session
def security(session: nox.Session) -> None:
    _install_tools(session)
    session.run("bandit", "-r", "src")


@nox.session
def secrets(session: nox.Session) -> None:
    _install_tools(session)
    session.run("detect-secrets", "scan", "--baseline", ".secrets.baseline")


@nox.session
def build(session: nox.Session) -> None:
    _install_tools(session)
    session.run("python", "-m", "build")


@nox.session
def docs(session: nox.Session) -> None:
    session.chdir(str(DOCS_DIR))
    package_lock = DOCS_DIR / "package-lock.json"
    if package_lock.exists():
        session.run("npm", "ci", external=True)
    else:
        session.run("npm", "install", external=True)
    session.run("npm", "run", "check", external=True)
    session.run("npm", "run", "build", external=True)
