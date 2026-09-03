# Real-Project Evidence

Validation date: 2026-09-03

This document tracks what AgentProof has been tested against outside its own
toy examples. The aim is not to make the project look bigger than it is. The
aim is to collect repeatable evidence from public, pinned agent-related
projects and reject anything that would make the data misleading.

Run the matrix:

```bash
python scripts/real_project_matrix.py
```

The script writes `real-project-matrix-results.json`.

Latest verified summary for AgentProof `0.1.1`:

| Metric | Value |
| --- | ---: |
| Public projects tested | 3 |
| AgentProof runs | 6 |
| Actual effects recorded | 8 |
| Intentional invariant failures caught | 2 |
| Duplicate side-effect failures caught | 2 |
| Inspected projects rejected from evidence count | 6 |

## What Counts

A project is included only when all of these are true:

- the repository is public;
- the commit is pinned;
- the tested boundary is a real exported tool or framework tool object;
- the side effect happens in the external project code first;
- AgentProof records effects by comparing actual external state before and
  after the external tool runs;
- the test does not require API keys, real user accounts, or production
  services.

## Included Projects

| Project | Pinned commit | Boundary | Real side effect | Result |
| --- | --- | --- | --- | --- |
| `aniket-work/Lets-Build-Online-Booking-System-Using-AI-Agents` | `7cc5937038ceb9d90a1212257d31233d265ef519` | LangChain `StructuredTool.invoke` | Appends to `streamlit.session_state.appointments` | AgentProof catches duplicate appointment under retry-after-commit |
| `extremecoder-rgb/medoraAI` | `26838fc355628e0383ae59dd8acf1b02ed2920e1` | LangChain `StructuredTool.invoke` | Updates an existing appointment in `streamlit.session_state.appointments` | AgentProof records one real reschedule and does not invent a duplicate |
| `Notnaton/oiv2` | `489923b679ab63d4edf2bd879e75486592a0c1fc` | Project-local `function_tool` wrapper | Appends to a file in an isolated temp repo | AgentProof catches duplicate file append under retry-after-commit |

## Rejected Projects

These projects were inspected but intentionally not included in the evidence
count:

| Project | Pinned commit | Reason rejected |
| --- | --- | --- |
| `kapa-ai/langchain-agent-example` | `c441a42c5956710d64e64a40bbea353a12db9afb` | Mock/read-only tools, not real state changes |
| `Hegazy360/langchain-multi-agent` | `0950344d913f30846321a31d0cc08b1f4c2bcfc1` | Live OpenAI/Tavily imports and placeholder mutation logic |
| `hungson175/mini-claw-code` | `2c22914b4c23242ff1c9d28d2bc6e4e0e3b5411a` | Starts an interactive live-LLM loop at import time |
| `AdityaUnal/RentalShop` | `add45b60fbe71ae170d720cf960348a889403e64` | Real SQLite writes exist, but import initializes HuggingFace/retriever stack |
| `cornflowerblu/strands-agent-shopper` | `9dfee90716811bf9cc1dcfc0e31480fe82d1b3ef` | Real cart operations require authenticated HEB account state |
| `sujay3srivastava/AI-Agent-Hackathon` | `13892eeda6e8afab083f58696301e8a00ab72a52` | Appointment tool is real, but page reads Streamlit secrets and calls OpenAI at import |

## How To Read The Result

In easy words:

- `projects_tested` is how many public projects were actually run.
- `agentproof_runs` counts baseline plus mutation runs.
- `effects_recorded` counts side effects AgentProof recorded after the external
  project code really changed state.
- `invariant_failures` are intentional failures where AgentProof caught unsafe
  behavior.
- `duplicate_side_effects_detected` means a retry caused the external project
  to do the action twice.

This is stronger than a demo because the side effects are not hard-coded inside
AgentProof examples. It is still not a mathematical proof that every agent app
will be safe. It is repeatable evidence across pinned public projects and
failure modes.
