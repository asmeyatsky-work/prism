# 0002 — Pinned lockfile via pip-tools

Status: Accepted
Date: 2026-05-12

## Context

Rules §4 ("Supply chain") requires lockfiles committed, dependency scans
in CI, signed commits on protected branches, and SBOM at build.

## Decision

We use `pip-tools` (`pip-compile`) to generate `requirements.lock` from
`pyproject.toml`. The lockfile pins exact versions of every transitive
dependency and is committed to the repo.

- Re-generation: `pip-compile -o requirements.lock pyproject.toml`
- CI installs from the editable project but verifies the lockfile via
  `pip-audit` against the locked set.
- SBOM is produced by `cyclonedx-py` in CI and uploaded as an artefact.

Alternatives considered: `uv lock` (faster, no transitive lockfile
guarantee yet); `poetry.lock` (rejected — extra runtime dependency).

## Consequences

- Bumping a dep requires running `pip-compile` and committing the
  refreshed lockfile.
- `pip-audit` runs against the lockfile in CI; new CVEs surface as PR
  failures.
