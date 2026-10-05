## Description

<!--
Write a short summary of the change: what problem does it fix, what feature
does it add, and why is it needed?

Reference related issues with `#issue_number` syntax, for example:
  - Fixes #123
  - Closes #45
  - Relates to #789
-->

- Fixes #
- Closes #

### What kind of change is this?

<!-- Tick all that apply. -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💔 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 🏗️ Refactor (non-breaking internal change; no user-visible behavior change)
- [ ] 📚 Documentation-only change
- [ ] 🧪 Tests / CI / DevOps
- [ ] 🧹 Chore (dependency updates, formatting, etc.)

## How was this tested?

<!-- Describe the tests that you ran. Add instructions so reviewers can
reproduce. Did you add new unit/integration/e2e tests? -->

```bash
# Paste test commands + output here
```

- [ ] I have added **unit tests** that prove my fix is effective or that my feature works.
- [ ] I have added **integration tests** (database/Qdrant/Redis/end-to-end).
- [ ] Existing tests still pass locally: `pytest tests/unit -q --cov=noesis`.
- [ ] Lint passes: `ruff check . && ruff format --check .`.
- [ ] Strict type-check passes: `mypy noesis`.

## Checklist:

- [ ] I have read the [Contributing Guide](CONTRIBUTING.md).
- [ ] My code follows the style guidelines of this project (PEP 8, ruff strict rules, strict mypy).
- [ ] All Pydantic types have `model_config = ConfigDict(extra="forbid")` where applicable.
- [ ] New public functions / classes have docstrings with `Parameters` / `Returns` sections.
- [ ] I have added / updated the relevant documentation in `README.md` or `docs/`.
- [ ] I have added new environment variables to `backend/.env.example` where applicable.
- [ ] This change introduces **no** backwards-incompatible changes to the public API.
- [ ] If this introduces a breaking change, I have **documented migration steps** below.

## Migration Guide (if breaking change)

<!--
What does a user upgrading from the previous version need to change?
Examples: renamed env vars, deprecated CLI flags, removed Python API.
-->

N/A
