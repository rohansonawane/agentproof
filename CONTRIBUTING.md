# Contributing

Run local checks before opening a change:

```bash
ruff format --check .
ruff check .
mypy src/agentproof
pytest -q
python -m build
twine check dist/*
```

Keep core dependencies small and keep framework integrations behind optional extras.

