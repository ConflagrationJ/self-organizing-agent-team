# Plan Review: <task_id>

## Review identity

| Field | Value |
|---|---|
| `task_id` | `<task_id>` |
| `reviewer` | `<agent-id>` |
| `base_rev` | `<revision>` |
| `contract` | `<path>` |
| `verdict` | `pass`, `conditional`, or `fail` |

## Review-time write attestation

- `reviewer_read_only_attested`: `true`
- `writes_during_review`: `false`
- `workspace_before_review`: `<revision or tree hash>`
- `workspace_after_review`: `<same revision or tree hash>`
- `write_check_evidence`: `<command output or log locator>`

## Credibility issues

List claims that are asserted but not evidenced. If none, write `None identified`.

## Findings

| ID | Severity | Trigger condition | Consequence | Counterexample | Required fix | Evidence |
|---|---|---|---|---|---|---|
| `F-1` | `high` | `<condition>` | `<impact>` | `<reproduction or scenario>` | `<required change>` | `<locator>` |

## Verified constraints

- Data boundary and single source of truth:
- Hard constraints versus weighted choices:
- Module interfaces and ownership:
- Concurrency, lock, idempotency, and ordering:
- Permission and authorization scope:
- External side effects:
- Rollback and failure recovery:
- Acceptance experiment:

## Unverified assumptions

- `<assumption and why it cannot be verified in plan review>`

## Execution-stage tests

- `<test that must run after implementation>`

## Verdict

- Decision: `pass`, `conditional`, or `fail`
- Conditions before implementation:
- High-severity issues remaining:
