# Publishing

Publication is manual. The release workflow can use PyPI Trusted Publishing/OIDC and does not store PyPI API tokens in the repository.

Publishing a GitHub Release triggers `.github/workflows/release.yml` to build and validate distributions, but it does not publish to PyPI. PyPI publishing only runs from a manual `workflow_dispatch` when `publish_to_pypi=true`.

## Package Name

Use `agentproof-sim` as the PyPI distribution name. Keep the Python import package and CLI as `agentproof`.

Reason: `agentproof` and `agentproof-ai` are already occupied on PyPI by unrelated projects, so publishing under either name would be impossible or misleading. The `agentproof-sim` name keeps the AgentProof brand while making the simulator/testing purpose clearer.

Expected user install command:

```bash
python -m pip install agentproof-sim
```

Expected Python import:

```python
import agentproof
```

Before publishing:

1. Confirm the PyPI project name.
2. Create or claim the `agentproof-sim` PyPI project under Rohan Sonawane's PyPI account.
3. Configure a Trusted Publisher for the exact GitHub owner, repository, workflow filename, and environment.
4. Prefer a protected `pypi` environment.
5. Build, check, install, and smoke-test the wheel in a clean environment.
6. Run live tests only with explicit credentials and `AGENTPROOF_RUN_LIVE_TESTS=1`.

Local package gate:

```bash
python -m build
twine check dist/*
python -m venv /tmp/agentproof-wheel-smoke
/tmp/agentproof-wheel-smoke/bin/python -m pip install dist/agentproof_sim-*.whl
/tmp/agentproof-wheel-smoke/bin/agentproof mutations
```

PyPI setup reminders:

- Do not create the project with an API token committed to GitHub.
- Prefer Trusted Publishing over stored PyPI tokens.
- Match the PyPI Trusted Publisher to owner `rohansonawane`, repository `agentproof`, workflow `.github/workflows/release.yml`, and environment `pypi`.
- Publish from Rohan Sonawane's own PyPI account only.
