# Contributing to Distill

Thanks for your interest in contributing to Distill!

## Development Setup

```bash
# Clone the repo
git clone https://github.com/nikpatel/distill.git
cd distill

# Install dependencies (requires uv: https://docs.astral.sh/uv/)
uv sync --all-extras

# Run tests
uv run pytest tests/ -x -q

# Lint and format
uv run ruff check src/ && uv run ruff format src/

# Type checking
uv run mypy src/ --no-error-summary
```

## Project Structure

```
src/                    # Source code (flat layout, import as distill.*)
  parsers/              # Session parsers (Claude, Codex, VerMAS)
  journal/              # Journal synthesis pipeline
  blog/                 # Blog generation + multi-platform publishing
  intake/               # Content ingestion (RSS, browser, social)
    parsers/            # Content source parsers
    publishers/         # Output format publishers
  cli.py                # CLI entry point (Typer)
  core.py               # Pipeline orchestration
tests/                  # Tests mirror source structure
```

## Code Style

- **Python 3.11+** with type hints throughout
- **Pydantic v2** for all models and config
- **ruff** for linting and formatting (line length 100)
- **mypy** strict mode for type checking
- Test files mirror source: `src/blog/foo.py` -> `tests/blog/test_foo.py`

## Making Changes

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Add tests for new functionality
4. Ensure all checks pass:
   ```bash
   uv run pytest tests/ -x -q
   uv run ruff check src/
   uv run ruff format --check src/
   ```
5. Open a pull request

## Adding a New Content Source (Parser)

1. Create `src/intake/parsers/your_source.py` implementing `ContentParser`
2. Add your source to `ContentSource` enum in `src/intake/models.py`
3. Add config model to `src/intake/config.py`
4. Register in `src/intake/parsers/__init__.py`
5. Add CLI flags in `src/cli.py` if needed
6. Write tests in `tests/intake/test_your_source_parser.py`

## Adding a New Publisher

1. Create `src/blog/publishers/your_platform.py` implementing `BlogPublisher`
2. Add to `Platform` enum in `src/blog/config.py`
3. Register in `src/blog/publishers/__init__.py`
4. Write tests in `tests/blog/test_your_platform.py`

## Conventions

- Optional dependencies use try/except with `_HAS_X` flags
- LLM calls go through `claude -p` subprocess (not API directly)
- All secrets come from environment variables, never hardcoded
- Test coverage target: 80%+

## Reporting Issues

Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version and OS
