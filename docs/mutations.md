# Mutations

Stable mutations have direct automated tests: `tool_timeout`, `timeout_after_commit`, `tool_error`, `tool_latency`, `rate_limited`, `malformed_response`, `missing_field`, `duplicate_user_request`, `stale_state`, `state_changed_after_read`, `permission_denied`, `delayed_event`, and `duplicate_event`.

`duplicate_tool_result` is implemented as an explicit duplicate-result envelope and marked experimental because framework semantics vary.

`reorder_tool_results` is not stable in this MVP. Installing it raises an unsupported-mutation error rather than pretending to reorder results outside a controlled parallel scheduler.

