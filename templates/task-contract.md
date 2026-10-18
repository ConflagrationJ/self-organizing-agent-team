# Task Contract

Replace the sample values with values for the current task. Keep exactly one fenced `json` block so the structure validator can parse it.

```json
{
  "contract_version": 1,
  "task_id": "TASK-2026-001",
  "task_goal": "Add retry-safe idempotent submission to a local job queue.",
  "non_goals": [
    "Do not deploy to production.",
    "Do not call a real webhook."
  ],
  "base_rev": "worktree-snapshot:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "risk": {
    "level": "high",
    "flags": [
      "concurrency",
      "external_side_effect",
      "network",
      "delete",
      "state_migration"
    ],
    "rationale": "Duplicate delivery, cleanup, and network delivery have external consequences."
  },
  "host_capabilities": {
    "delegation_available": true,
    "single_agent_fallback": true,
    "adapter": "host-delegation-v1",
    "detection": {
      "method": "runtime capability probe via host tool discovery",
      "observed": "delegation primitives are present in the current host",
      "evidence": "probe-host-capabilities.log#L1",
      "timestamp": "2026-10-18T12:00:00Z",
      "result": "available"
    },
    "fallback": {
      "method": "single-agent verification path",
      "observed": "main agent can perform a fresh review and test pass",
      "evidence": "fallback-verification.log#L1",
      "timestamp": "2026-10-18T12:00:00Z",
      "result": "available"
    }
  },
  "team": {
    "mode": "full_gate",
    "max_agents": 3,
    "max_parallel": 2,
    "coordinator": "main",
    "only_coordinator_can_spawn_or_close": true,
    "subagents_may_spawn": false,
    "reviewer_read_only": true,
    "author_reviewer_separated": true,
    "roles": [
      "writer",
      "reviewer",
      "executor"
    ],
    "assignments": {
      "writer": "agent-writer",
      "reviewer": "agent-reviewer",
      "executor": "agent-executor"
    }
  },
  "write_scope": [
    "src/queue.py",
    "tests/test_queue.py"
  ],
  "gates": {
    "plan_review": true,
    "code_review": true,
    "independent_execution": true
  },
  "acceptance": [
    {
      "id": "AC-1",
      "criterion": "Repeated submission does not duplicate delivery.",
      "method": "command",
      "command": "python -m unittest tests.test_queue",
      "evidence": "Command, exit code, timestamp, raw output, and artifact hash."
    },
    {
      "id": "AC-2",
      "criterion": "Cleanup removes only expired files inside the test fixture.",
      "method": "artifact",
      "command": "",
      "evidence": "Before-and-after fixture inventory bound to the reviewed revision."
    }
  ],
  "authorization": {
    "approval_required": true,
    "requested_actions": [
      "call-mock-webhook",
      "delete-expired-test-files",
      "apply-state-migration"
    ],
    "approved_actions": [],
    "stop_before_action": true,
    "note": "Execution remains blocked until each concrete action and target is approved."
  },
  "budget": {
    "max_rounds": 2,
    "agent_timeout_minutes": 30,
    "total_time_minutes": 90,
    "no_progress_rounds": 2,
    "escalation": [
      "split",
      "replan",
      "reduce_scope",
      "ask_user"
    ]
  },
  "evidence_requirements": {
    "bind_task_id": true,
    "bind_base_rev": true,
    "require_artifact_sha256_or_locator": true,
    "require_command_and_exit_code": true,
    "require_timestamp": true,
    "require_raw_output": true,
    "invalidate_on_artifact_change": true
  }
}
```

## Contract checklist

- Risk level is the higher plausible level.
- `write_scope` contains only project-relative paths.
- Medium and high risk use an independent reviewer.
- High risk requires plan review before writing and independent execution after review.
- Every external or irreversible action appears in `authorization.requested_actions`.
- Acceptance items name a command, artifact, or manual check and the evidence required.
