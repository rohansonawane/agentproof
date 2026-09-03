# Security

AgentProof is a testing framework for tool-using AI agents. It helps developers find unsafe action behavior in simulated environments, but it is not a sandbox, permissions system, or production safety layer.

## Security Model

AgentProof assumes your test suite is trusted Python code. Scenario functions, tool handlers, invariants, and adapter code execute with the same operating-system permissions as the test process.

AgentProof is designed to protect against logic failures such as:

- duplicate side effects after retry;
- actions that proceed after stale reads;
- unsafe behavior after malformed or missing tool data;
- incorrect handling of rate limits, timeouts, and tool errors;
- regressions in idempotency and permission checks.

AgentProof is not designed to protect against:

- malicious Python code in tests;
- untrusted third-party packages imported by tests;
- prompt injection in a live external system;
- misuse of production API credentials;
- secrets intentionally placed in non-obvious fields;
- real-world side effects caused by test code calling production services.

## Safe Usage

Use virtual tools, fakes, local simulators, or isolated staging services. Do not point AgentProof test runs at production systems for refunds, payments, email, account changes, file deletion, deployments, or other destructive operations.

Recommended precautions:

- Run tests with least-privilege credentials.
- Keep live provider tests opt-in and separate from deterministic CI.
- Use throwaway test accounts for live model smoke tests.
- Never commit API keys or tokens to the repository.
- Never paste secrets into examples, issue reports, trace excerpts, or README snippets.
- Review generated JSON, JUnit, replay, and trace artifacts before publishing them.
- Treat generated artifacts as potentially sensitive if your scenarios include customer data or internal business payloads.

## Secrets And Redaction

Trace and report serialization redacts obvious secret keys by key name, including `api_key`, `authorization`, `token`, `password`, and `secret`.

This is best-effort protection, not comprehensive data-loss prevention. AgentProof cannot know every sensitive field in your app. For example, fields such as `customer_email`, `account_number`, `medical_note`, or `internal_case_summary` may be sensitive even if their names do not look like credentials.

Prefer synthetic data in scenarios and avoid placing secrets in `world.state`, `world.metadata`, tool inputs, tool outputs, effect payloads, or invariant failure messages.

## Live LLM Tests

Live tests may send prompts, tool names, tool schemas, and relevant context to the configured model provider. They are skipped by default and require explicit opt-in:

```bash
# Set OPENAI_API_KEY through your shell, CI secret manager, or local secret manager first.
AGENTPROOF_RUN_LIVE_TESTS=1 pytest -m live -v
```

Use temporary environment variables, CI secrets, or a secret manager. Do not store live API keys in source files.

## Reporting Vulnerabilities

Please report security issues privately to the project maintainer before opening a public issue.

When reporting, include:

- affected version or commit;
- minimal reproduction steps;
- whether any generated artifacts contain sensitive data;
- whether real external services were called.
