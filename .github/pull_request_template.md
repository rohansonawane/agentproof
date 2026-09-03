## Summary

Describe what changed and why.

## Risk

Describe the behavior that could break, including any mutation, replay, report, or adapter boundary affected.

## Validation

- [ ] `ruff format --check .`
- [ ] `ruff check .`
- [ ] `mypy src/agentproof`
- [ ] `pytest -q`
- [ ] `python -m build`
- [ ] `twine check dist/*`

## Safety

- [ ] No API keys, tokens, customer data, or production payloads are committed.
- [ ] Tests do not call real destructive external services.
- [ ] New public claims are backed by implementation and tests.
- [ ] Live-provider behavior remains opt-in and is not required for deterministic CI.

## Notes

Add links to issues, replay artifacts, reports, or release validation notes when useful.
