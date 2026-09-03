# Production Readiness

AgentProof can help teams prepare tool-using agents for production, but AgentProof itself should be treated as a `0.1.0` technical preview until the API has more external adoption.

This document separates two questions:

- Can you use AgentProof in a production engineering workflow?
- Is AgentProof a production runtime safety layer?

The answer to the first is yes, with the controls below. The answer to the second is no.

## Recommended Production Workflow

Use AgentProof before deployment:

1. Model each risky external action as an AgentProof tool.
2. Make tool handlers commit explicit `EffectDraft` records only when the simulated side effect actually happens.
3. Add invariants for money, bookings, messages, permissions, approvals, files, and external spend.
4. Run the suite locally while developing.
5. Run deterministic tests in CI without API keys.
6. Fail CI with `agentproof run ... --fail-on high`.
7. Store replay artifacts for deterministic failures.
8. Keep live LLM smoke tests separate and opt-in.

## Minimum Controls For Real Apps

Before using AgentProof to approve an agent release, make sure:

- every destructive production tool has a virtual or staging equivalent;
- every high-risk action has at least one invariant;
- retries use idempotency keys where the real service supports them;
- worlds are reset between runs;
- reports are reviewed for sensitive data before sharing;
- live provider tests use least-privilege keys and throwaway accounts;
- CI can run without `OPENAI_API_KEY` or other external credentials;
- release decisions do not depend only on an LLM judge;
- failures can be replayed from saved seed and mutation configuration.

## What Is Already Automated In This Repository

The current repository validates:

- deterministic native execution;
- `timeout_after_commit` double-side-effect detection;
- idempotent retry protection;
- stable mutation behavior;
- isolated worlds between runs;
- replay from saved artifacts;
- JSON and JUnit failure reporting;
- CLI exit codes for CI gating;
- OpenAI Agents SDK adapter boundary using real SDK objects;
- LangChain/LangGraph adapter boundary using real framework objects;
- keyless deterministic CI;
- opt-in live OpenAI smoke testing;
- clean wheel build and install;
- executable README quickstart;
- real external LangChain booking-app smoke test.

## GitHub Repository Controls

The public GitHub repository is configured with:

- CI on pushes, pull requests, and manual workflow dispatch;
- required `main` branch status checks for Python 3.11, 3.12, and 3.13;
- linear history on `main`;
- force pushes and branch deletion disabled on `main`;
- issue templates for bug reports and feature requests;
- a pull request template with validation and safety checklists;
- Dependabot version update configuration for Python packages and GitHub Actions;
- Dependabot security updates enabled;
- secret scanning and push protection enabled where GitHub supports them;
- wiki disabled so documentation stays versioned in the repository.

## Current Limits

Do not overstate the project:

- AgentProof does not sandbox untrusted Python.
- It does not replace production authorization, monitoring, or approval systems.
- Secret redaction is best-effort, not comprehensive DLP.
- Live LLM behavior is not perfectly replayable.
- `reorder_tool_results` is intentionally unsupported in this MVP.
- No hosted dashboard, SaaS runner, or policy engine exists yet.
- API stability is technical-preview level, not long-term enterprise-stable.

## Release Gates

Run these before a public release:

```bash
ruff format --check .
ruff check .
mypy src/agentproof
pytest -q
python scripts/release_hardening.py
python scripts/real_project_booking_smoke.py
```

For live validation:

```bash
# Set OPENAI_API_KEY outside the command first.
AGENTPROOF_RUN_LIVE_TESTS=1 python scripts/release_hardening.py --live
```

For hosted CI validation:

```bash
python scripts/release_hardening.py --github
```

## Production-Ready Claim

The honest public claim today is:

> AgentProof is a technical-preview testing framework that can be used in production engineering workflows to test simulated tool-side effects before release.

The claim should not be:

> AgentProof is a complete production safety system for live autonomous agents.
