
# Copilot instructions — Tip-and-hours-Calculator- (Python-focused)

Purpose
- Provide an AI coding agent concise, actionable guidance for working on this repository when it targets Python. These instructions assume a small calculator-style app (tip/hour calculations) and focus on Python-specific workflows, file layout, and commands.

Initial discovery (what to look for)
- Files to find first: `pyproject.toml`, `requirements.txt`, `setup.cfg`, `Pipfile`, `README.md`, `src/`, `app.py`, `main.py`, `calculator.py`, `tests/`, and `.github/workflows/`.
- If `pyproject.toml` exists prefer its build/test configuration (e.g., `[tool.pytest]`, `build-system`). If only `requirements.txt` exists, use a venv + `pip` workflow.

Python runtime & environment (PowerShell examples)
- Create and activate venv, install deps:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
```

- Run tests (preferred):

```powershell
python -m pytest -q
```

- Run a simple module/CLI entry (if `app.py` or `main.py` present):

```powershell
python -m app
# or
python main.py
```

Testing & CI patterns
- Look for `tests/` with `tests/test_*.py` files and `pytest.ini` / `tox.ini` / `pyproject.toml` pytest section. Use `pytest` as the primary test runner.
- In CI (`.github/workflows/`), expect job steps like `actions/setup-python` + `pip install -r requirements.txt` + `pytest`. Mirror those locally when reproducing failures.

Project layout & architectural notes
- Prefer a small library + CLI structure:
	- `src/` or top-level package (e.g., `calculator/`) contains pure functions and business logic (tax/tip math, rounding rules).
	- `app.py` / `cli.py` contains argument parsing (`argparse`) and I/O glue code.
	- `tests/` contains unit tests that import the package (avoid running CLI in unit tests except via integration tests).
- Keep business logic pure and side-effect-free so tests can assert numeric outputs easily (e.g., `calculate_tip(amount, percent) -> Decimal`). Use `decimal.Decimal` for money accuracy.

Styling, typing, and tools
- Check for `pyproject.toml` / `setup.cfg` for formatting rules. Common tools used:
	- `black` + `isort` for formatting
	- `flake8` or `ruff` for linting
	- `mypy` for optional typing checks
- Follow the repo's config files if present; otherwise default to `black` formatting and `pytest` for tests.

External services & network calls
- If external APIs or services are referenced in code or tests, do NOT call them during automated runs. Prefer mocking (`unittest.mock` or `responses`) and document credentials in `README.md` if needed.

When repository is empty or missing Python files
- Report which manifests are missing (e.g., `pyproject.toml`, `requirements.txt`, `tests/`). Offer these starter scaffolds for the user's choice:
	- Minimal Python CLI scaffold (`argparse`) with `calculator/` package, `app.py`, `tests/`, `requirements.txt`.
	- Minimal web UI scaffold using `Flask` (if user asks for a web interface).

Editing and PR guidance
- Make minimal, focused changes and add tests for behavior changes. Use the same test commands found in CI when validating locally.
- In PR descriptions include: files changed, test command used, and one-line rationale for the change.

Files to reference when making changes
- `pyproject.toml` / `requirements.txt` — dependency and test config
- `src/` or package dir (e.g., `calculator/`) — business logic
- `app.py` / `main.py` / `cli.py` — entry points
- `tests/` — unit/integration tests
- `.github/workflows/` — CI steps to mirror locally

Questions to ask the repo owner (if unclear)
- Do you prefer `pyproject.toml` (poetry/flake8/mypy) or `requirements.txt` for dependency management?
- Should money use `decimal.Decimal` and explicit rounding rules, or is `float` acceptable for this project?
- Would you like a minimal Python CLI scaffold committed now so I can continue implementing features?

If anything above is incorrect, add a short `README.md` or reply and I will adapt these instructions.
