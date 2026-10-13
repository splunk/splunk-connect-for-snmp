# Agent instructions for Splunk Connect for SNMP (SC4SNMP)

This file gives AI agents and contributors enough context to work effectively in this repo. For deployment topology (Kubernetes/Docker Compose), Celery task flow (queues, chains, worker roles), and pipeline details, use **ARCHITECTURE.md** in addition to this file.

## What this project is

**Splunk Connect for SNMP** collects SNMP data and sends it to Splunk Enterprise and Splunk Cloud. It supports polling (scheduled walks) and trap ingestion, with configurable profiles and inventory.

- **Docs (deployed):** <https://splunk.github.io/splunk-connect-for-snmp/>
- **Support / contact:** [#splunk-connect-for-snmp](https://splunk-usergroups.slack.com/archives/C01K4V86WV7) on Slack

## Tech stack

- **Language:** Python 3.13–3.14 (see `pyproject.toml`)
- **Package manager:** Poetry
- **Runtime:** Celery workers, Redis, MongoDB
- **SNMP:** pysnmp python library (from Git: `pysnmp/pysnmp`, branch `main`)
- **Deployment:** Helm chart (Kubernetes), Docker Compose
- **Docs:** MkDocs (Material theme), versioned with Mike

## Repository layout

| Path | Purpose |
|------|--------|
| `splunk_connect_for_snmp/` | Directory containing all Python source code for the project |
| `test/` | Unit tests (mirrors package layout: `test/snmp/`, `test/splunk/`, etc.) |
| `integration_tests/` | Integration tests (Microk8s, Docker Compose); run with `[run-int-tests]` in commit message or on `develop` |
| `ui_tests/` | UI/E2E tests (pytest + Selenium-style); run with `[run-ui-tests]` in commit message or on `develop` |
| `charts/splunk-connect-for-snmp/` | Helm chart (values, templates, schema) |
| `docker_compose/` | Docker Compose setup |
| `docs/` | MkDocs source (`.md` files) |
| `mkdocs.yml` | MkDocs config and nav |
| `rendered/` | Rendered Helm manifests (generated; prefer editing chart/templates and re-rendering) |
| `examples/` | Example values and configs for Kubernetes |
| `dashboard/` | Dashboard/frontend assets if any |

## Development setup

1. **Install dependencies**
   ```bash
   poetry install
   ```

2. **Run unit tests**
   ```bash
   poetry run pytest --cov=./splunk_connect_for_snmp --cov-report=xml --junitxml=test-results/junit.xml
   ```
   Shorter: `poetry run pytest`

3. **Linting and formatting (pre-commit)**
   - Pre-commit is required before opening a PR.
   ```bash
   pre-commit run --all-files
   ```
   Hooks include: black, isort, pyupgrade, mypy (excluding `ui_tests`, `test*`, `docs`).

4. **Integration tests**
   - Triggered in CI when the commit message contains `[run-int-tests]` or when pushing to `develop` or `main`.
   - Run locally from `integration_tests/` (see workflows in `.github/workflows/ci-main.yaml` for env and flags).

5. **UI tests**
   - Located in `ui_tests/`.
   - Triggered in CI when the commit message contains `[run-ui-tests]` or when pushing to `develop` or `main`.
   - Run locally from `ui_tests/` (see workflows in `.github/workflows/ci-ui-tests.yaml` for env and flags).

## Conventions and PR expectations

- **Commits:** Use [Conventional Commits](https://www.conventionalcommits.org/). Common types: `feat`, `fix`, `chore`, `test`, `docs`.
- **Pre-commit:** Run and fix before pushing; CI runs it on `main`/`develop`.
- **Tests:** New behavior should be covered by unit tests; ensure existing tests pass.
- **Docs:** Update `docs/` (and `mkdocs.yml` nav if needed) for user-facing or deployment changes.
- **Helm:** When changing `charts/splunk-connect-for-snmp/` regenerate rendered manifests.

## Key entry points

- **CLI scripts** (from `pyproject.toml`): `traps`, `inventory-loader`, `run-walk`
- **Workers:** Celery apps and tasks in the main package (scheduler, poller, sender, traps).
- **Config:** YAML configs (e.g. `config.yaml` at repo root), Helm `values.yaml`, and profile YAML under `splunk_connect_for_snmp/profiles/`.

## Things to avoid

- Use `docker compose` (the modern CLI plugin), not the legacy `docker-compose` command.
- Do not add or rely on hardcoded credentials or secrets; use env vars or secret management.
- Do not edit `rendered/` as the source of truth; edit chart and docs source, then regenerate.
- Do not skip pre-commit or leave failing unit tests when submitting PRs.
- Always start new branch from the current state of the `develop` branch.
- Never push directly to `main` or `develop` without a PR and code review.
- Push at least one commit with `[run-int-tests]` in the message to trigger integration tests in CI before merging.
- Push at least one commit with `[run-ui-tests]` in the message to trigger UI integration tests in CI before merging.

## Documentation build (local)

```bash
poetry run mkdocs serve
```

Versioned docs are published via the `mike` workflow; see `.github/workflows/mike.yaml` and [MkDocs config](../mkdocs.yml).