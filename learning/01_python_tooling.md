# 01 — Python tooling

## The problem these tools solve

A Python project depends on a specific Python version and on many third-party packages. If you
install packages "globally", projects interfere with each other and the code works on one machine
but not on another. The tools below make the environment **reproducible** and the code
**checked automatically**.

## uv: Python versions, environments and packages

- **Virtual environment (venv):** a folder (`backend/.venv`) containing its own Python and its
  own installed packages. Nothing leaks in from, or out to, the rest of the computer.
- **uv** creates that environment, installs packages into it, and can even download Python
  itself. We set `python-preference = "only-managed"` so uv always uses its own CPython 3.12
  rather than the Microsoft Store Python, which behaves differently on Windows.
- **`pyproject.toml`** lists what the project needs (`dependencies`) and what only the developer
  needs (`dev` group: ruff, mypy, pytest...).
- **`uv.lock`** records the *exact* version of every package (including indirect ones). Anyone
  running `uv sync` gets the identical set → reproducible results, which matters for research.
- `uv run <command>` runs the command inside the venv without "activating" it.

## ruff: formatting and linting

- **Formatter** (`ruff format`): rewrites code into one consistent style, so diffs show real
  changes only.
- **Linter** (`ruff check`): finds likely bugs and bad patterns. Rule sets we enabled include
  `DTZ` (forbids timezone-naive datetimes — see note 05), `B` (common bugs), `I` (import order).

## mypy: static type checking

Python does not check types before running. mypy reads the type hints
(`def floor_to_minute(dt: datetime) -> datetime`) and reports mismatches *without running the
code*. We run it in **strict** mode: every function must be annotated. Example it caught in 1.4.1:
OpenCV's `imread` does not promise a `uint8` image, so we convert explicitly.

## pytest: automated tests

A test is a function starting with `test_` that uses `assert`. pytest finds and runs them all.

- **Fixtures** provide setup (e.g. a database session) to tests that ask for them by name.
- **Markers** label tests: `db` tests need PostgreSQL, `model` tests need downloaded weights.
  They are *skipped*, not failed, when that resource is absent, so the rest still runs.
- Database tests run inside a transaction that is **rolled back** afterwards, so tests never
  leave data behind and can run in any order.

## pre-commit

A git hook that runs ruff and mypy automatically before each commit, so broken code is caught
before it enters history. `scripts/check.ps1` runs everything (format check, lint, types, tests)
in one command.

## Viva questions

- **Why a lock file?** So the exact package versions behind every reported result can be
  reinstalled later; without it, a re-run months later might use different library versions.
- **What does strict typing buy you in Python?** Errors such as passing a naive datetime or a
  wrong array type are found before running, and the annotations document the interfaces.
- **Why are some tests skipped?** They need an external resource (database, model files). Skipping
  keeps the fast tests usable anywhere while still running the full set on the dev machine.
