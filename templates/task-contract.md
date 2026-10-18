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
      "method": "round-trip nonce probe through the host delegation tools",
      "observed": "spawn ran with history inheritance disabled, the child wrote the sha256 token digest, and follow-up reached the same child",
      "evidence": "probe-delegation.log#L1-L24",
      "timestamp": "2026-10-18T12:00:00Z",
      "result": "available",
      "probe": {
        "history_isolated": true,
        "same_child_confirmed": true,
        "workspace_visible": true,
        "initial_task_delivered": true,
        "write_succeeded": true,
        "followup_delivered": true,
        "token_a": "PROBEA7F3C1A9D2B",
        "token_b": "PROBEB2E48B6C1F7",
        "file_a": ".sot-tmp/probe-delegation-alpha.txt",
        "file_b": ".sot-tmp/probe-delegation-beta.txt",
        "evidence": "probe-delegation.log#L1-L24",
        "timestamp": "2026-10-18T12:00:00Z"
      }
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
- `delegation_available: true` requires a `detection.probe` whose six booleans are all true: `history_isolated`, `same_child_confirmed`, `workspace_visible`, `initial_task_delivered`, `write_succeeded`, `followup_delivered`.
- A host-preflight `delegation_available: false` sets `detection.method: "host preflight"`, `detection.result: "unavailable"`, records `observed`, `evidence`, and `timestamp`, omits `detection.probe`, and sets `fallback.result: "exercised"` after the single-agent pass.
- `probe.history_isolated` requires the probe to run with history inheritance disabled. An inherited parent history can contain `token_a`, which makes a fresh child look like it received the task.
- `probe.same_child_confirmed` requires the follow-up to land on the child that wrote `file_a`, proven by a value only that child knows.
- `probe.token_a` and `probe.token_b` must differ, and `probe.file_a` and `probe.file_b` must differ, so a cached or invented reply cannot pass.
- The probe carries its own `evidence` locator and `timestamp`, in addition to the detection record's.
