# Publishing

Publication is manual. The release workflow can use PyPI Trusted Publishing/OIDC and does not store PyPI API tokens in the repository.

Publishing a GitHub Release triggers `.github/workflows/release.yml` to build and validate distributions, but it does not publish to PyPI. PyPI publishing only runs from a manual `workflow_dispatch` when `publish_to_pypi=true`.

Before publishing:

1. Confirm the PyPI project name.
2. Configure a Trusted Publisher for the exact GitHub owner, repository, workflow filename, and environment.
3. Prefer a protected `pypi` environment.
4. Build, check, install, and smoke-test the wheel in a clean environment.
5. Run live tests only with explicit credentials and `AGENTPROOF_RUN_LIVE_TESTS=1`.
