# Contributing to Toolkit

This file is the canonical source of coding norms for all Flow Toolkit (`tk-*`)
repositories. It is written for human contributors and AI coding agents alike.
Other repositories link here instead of duplicating it.

## Workflow

- Fork or branch, make focused changes, and open a pull request against `master` or
 `main`.
- Keep pull requests small and limited to one concern. Do not reformat or refactor
  code unrelated to the change.
- CI must pass before a pull request is merged: linting, formatting, and the test
  suite.
- Add or update tests for every behavior change. See [tests/README.md](tests/README.md).

## Python version

- Target every Python version the repository currently supports. Check the CI
  configuration and package metadata rather than assuming one.
- Do not use syntax or standard library features unavailable in the oldest supported
  version.
- Code must work on every operating system Toolkit supports. See the
  [supported operating systems](https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_si_integrations_engine_supported_os_html).
- Code that runs inside a DCC must work with every DCC version Toolkit supports. See
  the [supported DCC engine versions](https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_si_integrations_engine_supported_versions_html).

## Code style

- Follow [PEP 8](https://peps.python.org/pep-0008/) and format with a
  [Black](https://black.readthedocs.io/)-compatible formatter. No whitespace on empty
  lines.
- tk-core enforces this with [Ruff](https://docs.astral.sh/ruff/) (`ruff check` and
  `ruff format`). Repositories not yet migrated use `black` and `flake8`. The
  `.pre-commit-config.yaml` of each repository is authoritative.
- Sort imports in three groups separated by a blank line: standard library,
  third-party, then local. Each group is alphabetical. Never use wildcard imports.
- Where order carries no meaning, keep class members, dictionary keys, and list
  literals in alphabetical order.
- Naming: `snake_case` for functions, methods, and variables; `PascalCase` for
  classes; a leading underscore for private members. Qt overrides keep Qt's
  `camelCase` names.
- Use American English (en-US) and regular hyphens (`-`), never typographic em dashes.

## Type annotations and docstrings

Much of the existing code predates type annotations. That is expected; do not
annotate untouched code as a standalone change.

- All new functions and methods must have inline type annotations.
- When you modify the signature of an existing function, annotate it in the same change.
- Use annotation syntax supported by the oldest Python version the repository targets.
- Public functions, methods, and classes need docstrings written in
  [reStructuredText](https://docutils.sourceforge.io/rst.html) using Sphinx field
  lists (`:param:`, `:returns:`, `:raises:`). [Sphinx](https://www.sphinx-doc.org/)
  generates the published documentation site from them. Annotations and docstrings
  coexist; do not repeat types in `:param:` lines.

```python
def resolve_path(template: Template, fields: dict, validate: bool = True) -> str:
    """
    Resolve a template path from the given fields.

    :param template: The template to resolve.
    :param fields: A mapping of token names to values.
    :param validate: Whether to validate the resolved path.
    :returns: The resolved filesystem path.
    :raises TankError: If a required field is missing.
    """
```

Static type checking (for example mypy) is not enforced in CI _yet_.

## Conventions

- Log with `LogManager.get_logger(__name__)`. Never use `print()` in library code.
- Import Qt through `tank.platform.qt` (`from tank.platform.qt import QtCore, QtGui`),
  never from PySide directly.
- Start every new source file with the copyright header used by neighboring files.
- Do not edit bundled third-party code (`tank_vendor`) or generated files (`ui/*.py`,
  `resources_rc.py`). Regenerate them with the repository's build tooling.
- Do not add new dependencies without discussing them in the pull request.
- Never include credentials, tokens, or site URLs in code, tests, or logs.
- Public GitHub content must not reference Autodesk-internal resources (internal
  wiki or ticket URLs). A bare ticket ID such as `SG-1234` is fine.

## Pre-commit hooks

Install [pre-commit](https://pre-commit.com/) hooks once per clone, then they run
on every commit:

```shell
pip install pre-commit
pre-commit install
```

Run them on the whole repository before pushing:

```shell
pre-commit run --all-files
```

## Commits and pull requests

- Commit and pull request titles and descriptions may be reused verbatim as release
  notes. Keep them concise, clear, and understandable by a user who has not seen the
  code.
- Title format: `SG-1234 Concise description` (omit the ticket ID if you have none).
  Use the imperative mood and describe the user-visible change, not the
  implementation (for example `SG-1234 Fix crash when a template has no fields`).
- Description: state what changed and why in a few sentences. Add how you tested it
  and mention any breaking change explicitly.

## Notes for AI coding agents

- Read this file and the repository's `.pre-commit-config.yaml` before writing code.
- Match the style of the surrounding code; make the smallest change that solves the task.
- Run `pre-commit run --all-files` and the tests, and fix failures before finishing.
- Do not push, force push, or merge unless explicitly asked.
