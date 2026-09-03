# Security

AgentProof executes developer-provided Python code during tests. It is not a sandbox for untrusted code.

Run AgentProof with least-privilege credentials and replace real production tools with virtual AgentProof tools. Examples and tests must not call real destructive services.

Trace and report serialization redacts obvious secret keys by key name, including `api_key`, `authorization`, `token`, `password`, and `secret`. This is not comprehensive DLP; developers remain responsible for sensitive payload design.

Live LLM tests may send prompts and tool schemas to the configured model provider. They are opt-in and skipped by default.

