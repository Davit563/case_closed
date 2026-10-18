# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

`case_closed` is a freshly scaffolded Python package with no features yet. The only code is `__version__` in `src/case_closed/__init__.py` and a smoke test.

## Rules

- Run `pytest` after every change and report the result.
- Keep code simple: this is a learning project. Prefer plain, readable Python over clever abstractions, extra dependencies, or premature structure.

## Commands

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # editable install + pytest

pytest                         # run all tests
pytest tests/test_smoke.py::test_version   # run a single test
```

There is no linter or formatter configured.

## Layout and conventions

- `src/` layout: package code lives in `src/case_closed/`, tests in `tests/`. pytest is configured in `pyproject.toml` (`pythonpath = ["src"]`), so tests import `case_closed` even without an install.
- Target Python is 3.9 (`requires-python = ">=3.9"`; the local interpreter is 3.9.6). Avoid 3.10+ syntax such as `match` statements and `X | Y` type unions at runtime.
- The version is defined in two places, `pyproject.toml` and `src/case_closed/__init__.py`, and `tests/test_smoke.py` asserts it. Update all three together when bumping.
