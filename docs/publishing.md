# Publishing

Publication is manual. The release workflow uses PyPI Trusted Publishing/OIDC and does not store PyPI API tokens in the repository.

Publishing a GitHub Release triggers `.github/workflows/release.yml` to build and validate distributions, but it does not publish to PyPI. PyPI publishing only runs from a manual `workflow_dispatch` when `publish_to_pypi=true`.

## Package Name

Use `agentproof-sim` as the PyPI distribution name. Keep the Python import package and CLI as `agentproof`.

Reason: `agentproof` and `agentproof-ai` are already occupied on PyPI by unrelated projects, so publishing under either name would be impossible or misleading. The `agentproof-sim` name keeps the AgentProof brand while making the simulator/testing purpose clearer.

Published project: https://pypi.org/project/agentproof-sim/

Expected user install command:

```bash
python -m pip install agentproof-sim
```

Expected Python import:

```python
import agentproof
```

## Published Release

`agentproof-sim==0.1.1` was published to PyPI on 2026-09-03 from GitHub Actions run `33805680882` using Trusted Publishing/OIDC.

External smoke test after publication:

```bash
python -m venv /tmp/agentproof-pypi-smoke
/tmp/agentproof-pypi-smoke/bin/python -m pip install --no-cache-dir agentproof-sim
/tmp/agentproof-pypi-smoke/bin/python -c "from importlib.metadata import version; import agentproof; print(version('agentproof-sim'), agentproof.__version__)"
```

Result: `0.1.1 0.1.1`.

## Future Releases

Before each future PyPI release:

1. Confirm the version has been bumped.
2. Run the local package gate below.
3. Run live tests only with explicit credentials and `AGENTPROOF_RUN_LIVE_TESTS=1`.
4. Publish from Rohan Sonawane's own PyPI account only.
5. Use the manual GitHub Actions `workflow_dispatch` path with `publish_to_pypi=true`.

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
- Keep the PyPI Trusted Publisher matched to owner `rohansonawane`, repository `agentproof`, workflow `.github/workflows/release.yml`, and environment `pypi`.
- Publish from Rohan Sonawane's own PyPI account only.
