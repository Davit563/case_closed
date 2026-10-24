# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

`case_closed` is a learning project: a mystery case (`cases/blackwood_manor/`) plus a hand-written Claude tool-use loop (`src/case_closed/agent.py`) that reads the evidence files and names the culprit. `solution.json` holds the answer and is hidden from the agent's tools.

## Rules

- Run `pytest` after every change and report the result.
- Keep code simple: this is a learning project. Prefer plain, readable Python over clever abstractions, extra dependencies, or premature structure.

## Commands

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # editable install + pytest

pytest                         # run all tests
pytest tests/test_smoke.py::test_version   # run a single test

python -m case_closed solve "Who stole the painting?"   # live run on blackwood_manor; needs an API key, costs money
python -m case_closed eval     # live run on every cases/*/ with a solution.json; prints "N/M solved, avg X tool calls"
```

Both commands take `--provider anthropic|openai` (before the command, e.g. `python -m case_closed --provider openai eval`). By default they use whichever key is set, `ANTHROPIC_API_KEY` first, then `OPENAI_API_KEY`. The Claude loop is in `agent.py` and the OpenAI loop is in `openai_agent.py`. They share the tools, system prompt and step limit. `OPENAI_MODEL` overrides the OpenAI model.

Tests never call the API: `tests/test_agent.py`, `tests/test_openai_agent.py` and `tests/test_eval.py` pass fake clients in. `eval` judges an answer by its last `Culprit: Full Name` line.

There is no linter or formatter configured.

## Layout and conventions

- `src/` layout: package code lives in `src/case_closed/`, tests in `tests/`. pytest is configured in `pyproject.toml` (`pythonpath = ["src"]`), so tests import `case_closed` even without an install.
- Target Python is 3.9 (`requires-python = ">=3.9"`; the local interpreter is 3.9.6). Avoid 3.10+ syntax such as `match` statements and `X | Y` type unions at runtime.
- The version is defined in two places, `pyproject.toml` and `src/case_closed/__init__.py`, and `tests/test_smoke.py` asserts it. Update all three together when bumping.
