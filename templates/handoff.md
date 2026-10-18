# Handoff: <task_id>

## Identity

| Field | Value |
|---|---|
| `task_id` | `<task_id>` |
| `role` | `writer`, `reviewer`, `executor`, `analyst`, or `monitor` |
| `owner` | `<agent-or-person-identifier>` |
| `base_rev` | `<immutable revision>` |
| `reviewed_revision` | `<revision reviewed, if applicable>` |
| `write_scope` | `<paths or none>` |
| `state` | `draft`, `ready_for_review`, `changes_requested`, `approved`, `executed`, or `aborted` |

## Original task inputs

- Task contract: `<path or stable locator>`
- Raw diff or files: `<path or stable locator>`
- Raw command logs: `<path or stable locator>`

Reviewers must receive these inputs before the writer's interpretation.

## Findings or changes

| ID | Severity | Claim or change | File and line | Status |
|---|---|---|---|---|
| `F-1` | `high`, `medium`, or `low` | `<finding>` | `<path:line>` | `open` or `closed` |

## Evidence

```json
[
  {
    "task_id": "TASK-2026-001",
    "base_rev": "worktree-snapshot:0123456789abcdef",
    "author": "agent-or-person-identifier",
    "artifact": "src/queue.py",
    "command": "python -m unittest tests.test_queue",
    "exit_code": 0,
    "timestamp": "2026-10-18T12:00:00Z",
    "scope": "queue retry tests",
    "artifact_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "artifact_locator": "",
    "raw_output": "exact output or stable log locator"
  }
]
```

## Review verdict

- Verdict: `pass`, `conditional`, `fail`, or `not_applicable`
- Conditions:
- Counterexample tested:
- Key evidence independently recomputed:

## Unresolved questions

- `<question and owner>`

## Stop or escalation

- Reason:
- Next allowed action:
