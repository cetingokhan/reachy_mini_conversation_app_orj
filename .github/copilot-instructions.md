# Copilot Instructions

**Before writing code, read [`AGENTS.md`](../AGENTS.md)** — it governs quality, naming, docs, and PR standards for this repository. This file covers the practical essentials: commands, architecture, and key conventions.

## Build, test, lint commands

```bash
# All checks (run before opening a PR)
ruff check . --fix && ruff format . && mypy --pretty --show-error-codes && pytest tests/ -v

# Individual checks
ruff check . --fix                    # Lint and auto-fix
ruff format .                         # Format
mypy --pretty --show-error-codes      # Type check (strict mode)
pytest tests/ -v                      # All tests
pytest tests/path/to/test.py -v      # Single test file
pytest -k "test_name" -v              # Single test by name
```

Config: `pyproject.toml` (Ruff line length 119, mypy strict, Python 3.12+).

## Architecture

**Entry point:** `src/reachy_mini_conversation_app/main.py` (CLI: `reachy-mini-conversation-app`)

**Realtime backends (loosely coupled):**
- `base_realtime.py` — abstract base, shared conversation loop
- `openai_realtime.py` — OpenAI Realtime (`gpt-4-realtime-preview`)
- `gemini_live.py` — Gemini Live (`gemini-3.1-flash-live-preview`)
- `huggingface_realtime.py` — Hugging Face (default)

**Key modules:**
- `conversation_handler.py` — wires audio, tools, backends
- `moves.py`, `dance_emotion_moves.py` — motion control
- `tools/` — LLM-callable tools (one file per tool, subclass `Tool` from `tools/core_tools.py`)
- `config.py`, `personality.py` — config + personality profiles

Built on the [Reachy Mini SDK](https://github.com/pollen-robotics/reachy_mini) (`reachy-mini>=1.8.3`). Use its public API only; don't fork or vendor internals.

## Key conventions

### Code quality
- **Names carry meaning:** Match the module's vocabulary; no `data`, `tmp`, `res`, `helper`.
- **Comments explain *why*:** One line, only where code can't speak for itself. Restate what the code does → delete it.
- **Docstrings on public APIs only, one line.** Must describe what the code *actually does*.
- **Log, don't print:** Use module `logger` with lazy `%`-style args (`logger.info("loaded %s", name)`), not f-strings. Reserve `print` for genuine CLI output.
- **Never swallow errors:** Catch the narrowest exception, log it, or let it propagate.

### Type hints
- **Modern typing:** `list[str]`, `dict[str, int]`, `X | None` (not `List`, `Optional`).
- **Avoid `Any` and `cast` in new code.** Model the real type.
- **No PEP 695 syntax** (`type Alias = ...`, `def f[T](...)`). Targets Python >=3.10.

### Tools (new tools go here)
- Subclass `Tool` from `tools/core_tools.py` in its own file.
- Define `name`, `description`, `parameters_schema`, and async `__call__(self, deps: ToolDependencies, **kwargs) -> dict`.
- Return `{"error": ...}` on failure instead of raising (graceful degradation).

### Tests
- `tests/` mirrors `src/` structure.
- Cover essential behavior (failing when behavior breaks, not on rename).
- Bug fix → add regression test. Feature → add happy-path test.

### Documentation
- **One README, one source of truth:** Never create another. Update root `README.md` if your change affects documented features, flags, config, or install steps.
- **Architecture diagram:** `docs/scheme.mmd` (Mermaid). Regenerate SVG when architecture changes; flag the need in the PR.

### PR expectations
- **Minimal diff, one fix/feature per PR.** Prefer deleting code to adding it.
- **Branch naming:** `<type>/<short-description>` or `<type>/<issue-number>-<short-description>`. Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
- **Issue first for features/non-trivial changes** (agree on approach before code exists).
- **Fill PR template** (don't rewrite it).
- **Update `.env.example` for new config vars.** Never commit secrets or `.env`.

### Dependencies
- Flag any new dependency before adding it.
- Keep `uv.lock` in sync: run `uv lock` after changing `pyproject.toml`.

### Style
- PEP 8 + Google Python Style Guide.
- Ruff enforces: line length 119, double quotes, isort `length-sort`.
- Cross-platform (Linux, macOS, Windows): no hardcoded paths or OS-only APIs without fallback.
