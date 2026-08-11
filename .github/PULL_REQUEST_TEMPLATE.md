<!--
Thanks for contributing to LLM Researcher! Please fill out the sections
below so maintainers can review your change quickly.

Before opening the PR, please:
- Read CONTRIBUTING.md — it covers setup, conventions, and the PR checklist.
- Check docs/ROADMAP.md — if this PR addresses a roadmap task, link it below.
- Make sure CI (ruff + pytest) is green; the same commands run locally per
  CONTRIBUTING.md (Testing & Linting).

For **security vulnerabilities**, do NOT open a public PR — report them
privately per SECURITY.md.
-->

## Summary

<!-- What does this PR do? One or two sentences. Reference the roadmap task
or issue it addresses, e.g. "Implements the 'Add GitHub pull request
template' task from Milestone 0 of docs/ROADMAP.md" or "Fixes #123". -->

## Type of change

<!-- Check all that apply. -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Refactor (no behavior change)
- [ ] Docs / community files
- [ ] CI / tooling
- [ ] Breaking change (fix or feature that changes existing behavior)

## How it was tested

<!-- Describe the tests you ran and the commands used, e.g.:

.venv/bin/python -m pytest tests/test_x.py -v
.venv/bin/ruff check app/
make frontend-build
-->

- [ ] Backend tests pass (`pytest tests/`)
- [ ] Ruff passes (`ruff check app/`)
- [ ] Frontend build / tests pass (if frontend changed)
- [ ] Manually verified (describe how)

## Checklist

<!-- Follow the full checklist in CONTRIBUTING.md (Pull Request Checklist). -->

- [ ] Branch is based on the latest `main`
- [ ] New behavior is covered by tests (bug fixes include a regression test)
- [ ] Docs updated where relevant ([README.md](README.md),
      [docs/PLAN.md](docs/PLAN.md), [docs/ROADMAP.md](docs/ROADMAP.md), etc.)
- [ ] No secrets or local artifacts (`.env`, `test.db`, build output) are
      committed — see [SECURITY.md](SECURITY.md)
- [ ] PR title and description clearly state the change and the roadmap task
      it addresses

## Screenshots / logs

<!-- If applicable, add screenshots or relevant log output. Redact any API
keys or secrets before pasting — never share credentials in pull requests
(see SECURITY.md). -->

## Additional context

<!-- Anything else maintainers should know: design decisions, follow-ups,
known limitations, or links to related issues/PRs. -->
