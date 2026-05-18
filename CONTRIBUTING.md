# Contributing to PowerStats

Thank you for considering contributing to PowerStats! This document outlines the process for contributing code, documentation, bug reports, and feature requests.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Ways to Contribute](#ways-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Submitting Changes](#submitting-changes)
- [Running Tests](#running-tests)
- [Commit Message Format](#commit-message-format)
- [Branching Strategy](#branching-strategy)

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## Ways to Contribute

- **Bug Reports** — Open an issue with the `bug` label. Include your OS version, Python version, and relevant logs from `journalctl --user -u powerstats.service`.
- **Feature Requests** — Open an issue with the `enhancement` label. Describe the use case clearly.
- **Documentation** — Improve README, inline docstrings, or add wiki pages.
- **Code** — Fix bugs, implement features, improve performance or test coverage.

---

## Development Setup

### Prerequisites

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-psutil upower
pip install pytest flake8 isort black
```

### Clone & Run

```bash
git clone https://github.com/powerstats/powerstats.git
cd powerstats/powerstats-1.0.0
python3 main.py
```

### Run Tests

```bash
python3 -m pytest tests/ -v
```

---

## Coding Standards

- **Style**: Follow [PEP 8](https://peps.python.org/pep-0008/). Max line length: 120.
- **Formatter**: Use `black` for formatting.
- **Imports**: Sorted with `isort`. Standard library → third-party → local.
- **Type Hints**: Add type hints to new public functions.
- **Docstrings**: Add docstrings to new public classes and functions.
- **No inline imports**: All imports must be at the top of the file.
- **Logging**: Use the module-level `log = logging.getLogger(...)` pattern. No bare `print()`.

---

## Submitting Changes

1. Fork the repository.
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes with tests.
4. Ensure CI passes: `make lint && make test`
5. Commit using [Conventional Commits](#commit-message-format).
6. Open a Pull Request against `master`.

---

## Running Tests

```bash
# All tests
python3 -m pytest tests/ -v --tb=short

# With coverage
python3 -m pytest tests/ --cov=. --cov-report=term-missing
```

---

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

[optional body]
[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

**Examples**:
```
feat(daemon): add multi-battery aggregation support
fix(analytics): correct duration overcounting in partial buckets
docs(readme): update installation instructions
perf(window): async-load analytics data to eliminate startup delay
```

---

## Branching Strategy

| Branch | Purpose |
|--------|---------|
| `master` | Stable, release-ready |
| `feat/*` | New features |
| `fix/*` | Bug fixes |
| `docs/*` | Documentation only |
| `release/v*` | Release preparation |
