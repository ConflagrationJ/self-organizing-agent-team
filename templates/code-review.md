# Code Review: <task_id>

## Review identity

| Field | Value |
|---|---|
| `task_id` | `<task_id>` |
| `reviewer` | `<agent-id>` |
| `author` | `<different agent-id>` |
| `base_rev` | `<base revision>` |
| `reviewed_revision` | `<exact revision reviewed>` |
| `write_scope` | `<paths>` |
| `verdict` | `pass`, `conditional`, or `fail` |

## Inputs received

- Original task contract: `<locator>`
- Raw diff or files: `<locator>`
- Raw command logs: `<locator>`
- Acceptance criteria: `<locator>`

## Findings

| ID | Severity | Trigger condition | Consequence | Counterexample | Required fix | Evidence |
|---|---|---|---|---|---|---|
| `F-1` | `high` | `<condition>` | `<impact>` | `<reproduction>` | `<required change>` | `<locator>` |

## Independently recomputed evidence

- Claim:
- Original evidence:
- Recomputation command:
- Recomputation result:

## Risk checks

- Path and write-scope boundaries:
- Secrets, PII, and logging:
- Timeout, cancellation, and late callbacks:
- Duplicate execution and idempotency:
- Empty, malformed, or oversized input:
- Partial failure and rollback:
- Unauthorized network or external action:

## Review-time write check

- Workspace unchanged during review: `yes` or `no`
- If `no`, this review is invalid.
- `reviewer_read_only_attested`: `true`
- `writes_during_review`: `false`

## Verdict

- Decision: `pass`, `conditional`, or `fail`
- Conditions before execution:
- High-severity issues remaining:
