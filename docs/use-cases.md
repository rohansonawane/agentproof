# Real-World Use Cases

AgentProof is most useful when an AI agent can change external state through tools. It belongs in pre-production test suites and CI gates, where risky actions can be simulated safely.

## Customer Support And Refunds

Use AgentProof to test refund, replacement, credit, and escalation agents.

Useful invariants:

- total refunded amount must not exceed the order total;
- a refund requires an eligible order state;
- the same customer request cannot create two refunds;
- retries must reuse an idempotency key.

Failure modes to inject:

- `timeout_after_commit` on `refund_order`;
- `rate_limited` on payment or commerce tools;
- `stale_state` after the agent reads an order;
- `malformed_response` from an order lookup.

## Booking And Scheduling

Use AgentProof for agents that book appointments, reserve seats, cancel events, or reschedule meetings.

Useful invariants:

- one user intent creates at most one booking;
- a canceled appointment is not also rescheduled;
- double-booking the same slot is forbidden;
- confirmation messages are sent only after a committed booking.

Failure modes to inject:

- `timeout_after_commit` on booking creation;
- `duplicate_user_request`;
- `state_changed_after_read` for availability;
- `duplicate_event` for reminder or webhook delivery.

## CRM And Sales Operations

Use AgentProof when agents create leads, update opportunities, assign owners, or send follow-up messages.

Useful invariants:

- lead creation is idempotent by email or external ID;
- high-value account changes require approval;
- a closed opportunity cannot be moved backward without a reason;
- automated outreach respects opt-out state.

Failure modes to inject:

- `permission_denied`;
- `missing_field` in account data;
- `stale_state` on lead or opportunity records;
- `tool_error` on CRM update.

## Email, Messaging, And Notifications

Use AgentProof for agents that send email, chat messages, support replies, or webhook notifications.

Useful invariants:

- a single user intent sends at most one external message per channel;
- sensitive content is not sent to the wrong recipient;
- messages are not sent before required approval;
- duplicate webhook delivery does not duplicate customer-visible output.

Failure modes to inject:

- `duplicate_event`;
- `tool_timeout` on send;
- `timeout_after_commit` on send;
- `malformed_response` from contact lookup.

## DevOps And Internal Automation

Use AgentProof for agents that modify infrastructure, deployments, tickets, repositories, or operational records.

Useful invariants:

- production actions require explicit approval;
- destructive actions are forbidden in default scenarios;
- a deployment cannot proceed after a failed validation step;
- file or repository changes stay inside allowed paths.

Failure modes to inject:

- `permission_denied`;
- `tool_error` from deploy or validation tools;
- `stale_state` on environment status;
- `duplicate_user_request`.

## Coding Agents

Use AgentProof to test agents that call file, git, issue, or CI tools.

Useful invariants:

- protected files are not modified;
- commits contain only intended paths;
- failed tests prevent publish or deploy actions;
- secrets are never written to generated reports.

Failure modes to inject:

- `tool_error` during tests;
- `missing_field` from issue metadata;
- `state_changed_after_read` for branch status;
- `delayed_event` for CI completion.

## Where Not To Use AgentProof

Do not use AgentProof as a runtime security boundary. It does not sandbox Python code, block production credentials, or enforce authorization in a live application.

Do not aim it directly at production payment, email, cloud, file deletion, or account-management APIs. Replace those tools with virtual AgentProof tools or isolated staging doubles.

AgentProof is a release and regression-testing tool. Your production app still needs real authorization, idempotency keys, audit logs, rate limits, monitoring, and human approval for high-risk actions.
