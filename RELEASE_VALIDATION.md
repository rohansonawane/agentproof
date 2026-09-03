# AgentProof Release Validation

Validation date: 2026-09-03  
Validator posture: independent senior-engineer audit before first public release  
Host: macOS / Darwin, Python 3.12.9

## Executive Result

The repository initially contained only `AGENTPROOF_CODEX_BUILD_SPEC.md`; `IMPLEMENTATION_PLAN.md`, `RELEASE_VALIDATION.md`, source, tests, packaging, and examples were absent. That was a release-blocking defect.

I implemented and validated a technical-preview `0.1.0` package with deterministic native execution, fault injection, replay, CLI, JSON/JUnit reports, pytest plugin, clean wheel install, local OpenAI/LangChain adapter-boundary coverage, and an opt-in live OpenAI Agents SDK smoke test.

Release readiness is **technical preview only**, not full public-stable approval, because PyPI project ownership was not verified, no live LangChain provider test exists, and `reorder_tool_results` remains unsupported rather than falsely implemented.

## Commands Run

| Command | Result |
| --- | --- |
| `python --version` | `Python 3.12.9` |
| `ruff format --check .` | PASS, `82 files already formatted` |
| `ruff check .` | PASS, `All checks passed!` |
| `mypy src/agentproof` | PASS, `Success: no issues found in 40 source files` |
| `pytest -q` | PASS, `53 passed, 1 skipped` |
| `env -u OPENAI_API_KEY -u AGENTPROOF_RUN_LIVE_TESTS pytest -q -m 'not live'` | PASS, `53 passed, 1 deselected` |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p pytest_asyncio.plugin -p pytest_cov --cov=agentproof --cov-report=term-missing` | PASS, `53 passed, 1 skipped`, total coverage `90%` |
| `python -m build` | PASS, built `agentproof-0.1.0.tar.gz` and `agentproof-0.1.0-py3-none-any.whl` |
| `twine check dist/*` | PASS for wheel and sdist |
| `pytest --trace-config -q` | PASS, `agentproof.pytest_plugin` registered |
| `python scripts/release_hardening.py` | PASS, `13` checks passed, `2` opt-in checks skipped |
| `gh run watch 33746954869 --repo rohansonawane/agentproof --exit-status` | PASS, GitHub-hosted CI matrix passed on Python 3.11, 3.12, and 3.13 |
| `python scripts/real_project_booking_smoke.py` | PASS, real external booking-agent tool produced duplicate side effects under retry and AgentProof caught it |
| `python scripts/real_project_matrix.py` | PASS, 3 pinned public projects, 6 AgentProof runs, 8 actual effects recorded, 2 duplicate side-effect failures caught |

## Clean-Environment Results

Core wheel smoke:

```text
pip install dist/agentproof-0.1.0-py3-none-any.whl
agentproof mutations
python readme_quickstart.py
```

Result: PASS. The installed CLI listed mutations, and the README quickstart printed:

```text
INVARIANT_FAILURE
['no_double_refunds']
98.0
```

Optional extras clean solve:

```text
pip install 'dist/agentproof-0.1.0-py3-none-any.whl[openai,langchain]'
```

Result: PASS.

```text
openai-agents 0.22.0 FunctionTool
brotli 1.2.0
langchain 1.3.18 True
langgraph 1.2.11 ToolNode
```

External toy-project smoke:

```text
python scripts/release_hardening.py
```

Result: PASS. The automation installed the built wheel into an independent temporary project, ran a separate billing-agent suite through the installed `agentproof` CLI, verified the command failed with exit code `1`, parsed JSON/JUnit output, and confirmed two actual `payment.charged` effects.

Real external-project smoke:

```text
python scripts/real_project_booking_smoke.py
```

Target: `aniket-work/Lets-Build-Online-Booking-System-Using-AI-Agents` at commit `7cc5937038ceb9d90a1212257d31233d265ef519`.

Result: PASS. The script cloned the Apache-2.0 project into a temporary directory, installed AgentProof and minimal dependencies in a clean virtual environment, imported the project's real LangChain `book_appointment` tool, and wrapped its actual `streamlit.session_state.appointments` mutation as an AgentProof effect. Baseline produced one `appointment.booked` effect. With `TimeoutAfterCommit(target="book_appointment")`, the retrying agent produced two real appointments at the same time, and AgentProof reported `INVARIANT_FAILURE` for `no_duplicate_appointments`.

Real public-project matrix:

```text
python scripts/real_project_matrix.py
```

Result: PASS. The script created a temporary virtual environment, installed AgentProof from the local checkout, cloned pinned public repositories, invoked real exported tool boundaries, and recorded effects only after external project state changed. It wrote `real-project-matrix-results.json`.

Summary:

```text
projects_tested: 3
agentproof_runs: 6
effects_recorded: 8
invariant_failures: 2
expected_failures_detected: 2
duplicate_side_effects_detected: 2
```

Included:

| Project | Pinned commit | Boundary | Result |
| --- | --- | --- | --- |
| `aniket-work/Lets-Build-Online-Booking-System-Using-AI-Agents` | `7cc5937038ceb9d90a1212257d31233d265ef519` | LangChain `StructuredTool.invoke` | Duplicate appointment creation caught under retry-after-commit |
| `extremecoder-rgb/medoraAI` | `26838fc355628e0383ae59dd8acf1b02ed2920e1` | LangChain `StructuredTool.invoke` | One real reschedule recorded; retry did not create an inferred duplicate |
| `Notnaton/oiv2` | `489923b679ab63d4edf2bd879e75486592a0c1fc` | Project-local `function_tool` wrapper | Duplicate file append caught under retry-after-commit |

Rejected from the evidence count after inspection: `kapa-ai/langchain-agent-example`, `Hegazy360/langchain-multi-agent`, `hungson175/mini-claw-code`, `AdityaUnal/RentalShop`, `cornflowerblu/strands-agent-shopper`, and `sujay3srivastava/AI-Agent-Hackathon`. Reasons are documented in `docs/real-project-evidence.md`; the common problems were mock/read-only tools, live API/account requirements, unsafe import-time behavior, or placeholder side effects.

## Required Verification Checklist

| Requirement | Result | Evidence |
| --- | --- | --- |
| `TimeoutAfterCommit` performs the side effect before returning timeout | PASS | `tests/unit/test_tool_faults.py::test_timeout_after_commit_commits_effect_then_times_out`; trace order is `effect < fault < tool_error` |
| Naive refund agent creates two refunds under retry | PASS | `tests/integration/test_refund_acceptance.py::test_timeout_after_commit_exposes_double_refund`; 2 effects, `$98.00` |
| Idempotent refund agent prevents duplicate | PASS | `tests/integration/test_refund_acceptance.py::test_idempotency_survives_timeout_after_commit`; 1 effect, idempotency key preserved |
| EffectLedger reflects actual simulated effects, not inferred tool calls | PASS | `tests/unit/test_effects_world_invariants.py::test_effect_ledger_records_actual_effects_not_tool_calls` |
| Every documented stable mutation has implementation and tests | PASS for stable set | Direct unit tests cover all stable mutations listed below |
| Replay uses saved seed/configuration | PASS | CLI replay and `tests/integration/test_replay_and_reports.py::test_replay_reproduces_failure_from_saved_seed_and_source` |
| Worlds isolated between runs | PASS | `tests/integration/test_refund_acceptance.py::test_worlds_are_isolated_between_mutation_runs` |
| OpenAI Agents SDK integration uses real SDK boundary | PASS | Actual `agents.FunctionTool` constructed and invoked locally; opt-in live OpenAI smoke passed |
| LangChain/LangGraph integration uses current real framework APIs | PASS local boundary | Actual `StructuredTool`, `create_agent` import, compiled `StateGraph` + `ToolNode` execution |
| Deterministic CI requires no API keys | PASS | keyless `pytest -q -m 'not live'` passed |
| Live tests are opt-in | PASS | `tests/e2e/test_live_opt_in.py` requires `AGENTPROOF_RUN_LIVE_TESTS=1` and `OPENAI_API_KEY` |
| Secrets redacted from traces/reports | PASS | `tests/unit/test_redaction.py` |
| CLI exit codes fail CI | PASS | `agentproof run ... --fail-on high` exited `1` for high-severity double refund |
| JSON/JUnit reports contain truthful failure information | PASS | JSON: 2 total, 1 failed, `no_double_refunds`, 2 refund effects; JUnit: `tests=2 failures=1 errors=0` |
| Built wheel installs and runs in clean environment | PASS | Clean venv installed wheel, ran CLI and README quickstart |
| README examples execute | PASS | `tests/integration/test_readme_examples.py` and clean-wheel smoke |
| No critical functionality is stub/TODO/fake/test-only | PARTIAL | No `TODO`/`NotImplemented` found in source; `reorder_tool_results` is explicitly unsupported/experimental, not claimed stable |

## Mutation Coverage

| Mutation | Unit Tested | Integration Tested | Adapter Coverage | Status |
| --- | --- | --- | --- | --- |
| `tool_timeout` | Yes | Native refund retry | Native | Stable |
| `timeout_after_commit` | Yes | Native refund duplicate/idempotent/replay/CLI | Native, OpenAI callback | Stable |
| `tool_error` | Yes | No broad scenario | Native registry | Stable |
| `tool_latency` | Yes | No broad scenario | Native registry | Stable |
| `rate_limited` | Yes | No broad scenario | Native registry | Stable |
| `malformed_response` | Yes | No broad scenario | Native registry | Stable |
| `missing_field` | Yes | No broad scenario | Native registry | Stable |
| `duplicate_user_request` | Covered through controller behavior | No broad scenario | Native runner | Stable |
| `stale_state` | Yes | No broad scenario | Native registry | Stable |
| `state_changed_after_read` | Yes | No broad scenario | Native registry | Stable |
| `permission_denied` | Yes | No broad scenario | Native registry | Stable |
| `delayed_event` | Yes | No broad scenario | Event queue | Stable |
| `duplicate_event` | Yes | No broad scenario | Event queue | Stable |
| `duplicate_tool_result` | Yes | No broad scenario | Native registry | Experimental |
| `reorder_tool_results` | Unsupported behavior tested | No | None | Experimental/unsupported |

## Defects Found And Fixed During Audit

- Missing implementation, tests, implementation plan, and validation report.
- `ToolTimeoutError` did not initially subclass Python `TimeoutError`, so normal retry handlers would not catch it.
- `python -m agentproof.cli` initially did nothing because the CLI module lacked an entry guard.
- CLI-created `timeout_after_commit` mutations defaulted to medium severity, so `--fail-on high` did not fail CI.
- Dynamic CLI/replay imports were not registered in `sys.modules`, breaking module-level invariant discovery.
- LangGraph `ToolNode` integration needed compiled `StateGraph` execution in the tested API version.
- `twine check` with Twine 6 rejected Hatchling metadata version `2.5`; dev tooling was updated to Twine 7 and Rich bound widened to `<16`.
- README quickstart was changed to avoid leaving artifacts during example-test execution.
- Live OpenAI execution failed in this environment with `brotli==1.0.9` because `httpx2` expects Brotli transport support compatible with `httpx2[brotli]`; the `openai` extra now requires `httpx2[brotli]>=2.12,<3` and the optional-extras smoke asserts `brotli 1.2.0`.
- `scripts/release_hardening.py --live` initially allowed ordinary pytest, coverage, and plugin-trace gates to consume live credentials repeatedly; only the dedicated live gate now runs live tests.

## Third-Party Documentation Verified

- OpenAI Agents SDK guide: https://developers.openai.com/api/docs/guides/agents
- OpenAI Agents SDK quickstart: https://developers.openai.com/api/docs/guides/agents/quickstart
- LangChain agents guide: https://docs.langchain.com/oss/python/langchain/agents
- LangChain tools guide: https://docs.langchain.com/oss/python/langchain/tools
- LangGraph v1 migration guide: https://docs.langchain.com/oss/python/migrate/langgraph-v1

## Automated Follow-Up

`scripts/release_hardening.py` now automates the repeatable local release gate. It runs format, lint, type checking, pytest with live tests disabled, keyless pytest, coverage with live tests disabled, build, Twine metadata validation, clean core wheel smoke, README quickstart smoke, optional OpenAI/LangChain extras install smoke, independent external toy-project smoke, pytest plugin registration tracing with live tests disabled, and a dedicated opt-in live gate. It writes machine-readable results to `release-hardening-results.json`.

`scripts/real_project_booking_smoke.py` adds a networked manual launch-confidence check against a pinned public repo. It is intentionally separate from default CI because it depends on GitHub availability and a third-party repository.

`scripts/real_project_matrix.py` extends that launch-confidence check to multiple pinned public projects. It remains intentionally outside default CI because it clones third-party repositories and installs their dependencies, but it is deterministic after GitHub checkout and requires no API keys.

Live model tests and hosted GitHub Actions are intentionally not automatic by default. Use `--live` with `AGENTPROOF_RUN_LIVE_TESTS=1` and credentials for live tests, and `--github` with a git repository plus authenticated `gh` CLI for hosted CI triggering. On 2026-09-03, the OpenAI live smoke test passed with user-supplied credentials, and GitHub-hosted CI passed after pushing to `rohansonawane/agentproof`.

## Known Limitations

- The OpenAI live smoke test passed, but no live LangChain provider test exists yet. Live tests remain opt-in.
- Real-project evidence currently covers 3 public pinned projects. That is useful launch evidence, not a statistical guarantee across the agent ecosystem.
- PyPI project ownership and Trusted Publisher configuration were not verified.
- `reorder_tool_results` is not stable and intentionally raises unsupported instead of pretending to work.
- `duplicate_tool_result` is implemented as a deterministic duplicate-result envelope but remains experimental because framework agent-loop semantics vary.
