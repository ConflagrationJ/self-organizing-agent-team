---
name: self-organizing-agent-team
description: Coordinate a risk-based, minimal multi-agent workflow with explicit ownership, write scopes, review gates, revision-bound evidence, and user authorization for external side effects. Use for multi-step delivery that spans code, data, or external operations; use the single-agent path when the task is low risk or delegation is unavailable.
---

# Self-Organizing Agent Team

Use this skill to choose the smallest safe team for a delivery task, not to create a team by default.

## First: detect host capability

Check which delegation mechanism the current host actually exposes. Do not assume a particular tool name, syntax, or nesting model. If the host ships a documented adapter, read it before creating anything. Host policy, sandbox, and approval controls always take precedence over this protocol. If no usable delegation mechanism exists:

1. Run the work as a single agent.
2. Perform a separate verification pass after implementation: reread the diff, run tests, and record evidence.
3. State explicitly that no subagents were created. Never imply that a team was formed.

Record the result in the task contract under `host_capabilities`, including the detection method, observed result, evidence locator, timestamp, and a fallback record (`available`, or `exercised` when delegation is unavailable). A string such as `runtime-detected` is not evidence.

## Risk routing

Choose the higher risk level when evidence is mixed. The coordinator may reduce scope, but may not reduce the gate level below the risk.

| Risk | Typical trigger | Team | Required gates |
|---|---|---|---|
| Low | One local file or one narrow test; no shared interface; reversible | No subagents. The main agent implements and verifies. | Scope check, relevant tests, evidence |
| Medium | Two or more modules; shared interface; moderate regression risk; reversible | At most 2 subagents: writer plus independent reviewer | Code review, tests, revision-bound evidence |
| High | Concurrency, locks, permissions, secrets, migrations, network, deletion, publication, payment, production, or other external side effects | At most 3 subagents: writer, independent reviewer, executor | Plan review before writing, code review, independent execution, user authorization for each external action |

Do not delegate simple edits, read-only questions, or routine test additions merely because this skill was invoked.

## Non-negotiable invariants

- Only the coordinator may create, reassign, or close execution units. On hosts that allow peer messaging and a shared task board, peers may coordinate directly, but the coordinator still owns ownership, closure, and acceptance. Teammates must not create nested execution units.
- The writer and reviewer are different execution units. The reviewer receives the original task contract, base revision, raw diff or files, and raw logs, not the writer's conclusion first.
- Plan reviewers, code reviewers, and monitors are read-only. Any review-time write invalidates the review.
- Every delegated task has one contract, one task ID, one base revision, and an explicit `write_scope`.
- Every acceptance claim binds to a revision and an artifact hash or equivalent locator, plus the command, exit code, timestamp, and raw output where applicable.
- External side effects and irreversible actions require explicit user approval for the concrete action and target. Approval does not carry across tasks or expand silently.

## Gate order

1. Bind the base revision to a reproducible snapshot (`git rev-parse HEAD`, or `python scripts/snapshot_worktree.py .` when the workspace has no VCS revision), then write the task contract from `templates/task-contract.md`. If the host assigns its own work ids, create the host work item first and use the returned id as `task_id`.
2. Run the structural validator when a JSON contract block is present.
3. For high risk, complete plan review before code is written.
4. Implement only inside `write_scope`.
5. Complete code review against the exact reviewed revision.
6. Execute tests or the minimum safe probe from a separate executor.
7. Record acceptance evidence and any residual risk. Link handoff, acceptance, and artifact hashes through `templates/evidence-manifest.md` when those files exist.

## Stop rules

- Maximum two writer-reviewer rounds. On the second unresolved round, stop and escalate to the user.
- Stop immediately when the same blocker repeats without a new artifact, new evidence, or a changed plan.
- Stop on any unauthorized external action, review-time write, revision drift, missing approval, or evidence older than the reviewed revision.
- Escalation choices are limited to splitting the task, replanning, reducing scope, or asking the user.

## References

Read only what the current task needs:

- `references/role-catalog.md` for role permissions and handoff inputs.
- `references/scheduling-policy.md` for risk classification, dependency rules, budgets, states, and escalation.
- `references/evidence-and-gates.md` for evidence envelopes and review verdicts.
- `references/risk-and-authorization.md` for the external-action approval matrix.
Templates:

- `templates/task-contract.md`
- `templates/evidence-manifest.md`
- `templates/handoff.md`
- `templates/plan-review.md`
- `templates/code-review.md`
- `templates/acceptance.md`

## Validation boundary

`scripts/validate_task_contract.py` checks structure and, when `--manifest` is supplied, linked-file hashes and revision equality. It needs Python 3.8 or newer; when the host does not expose `python` on `PATH`, use the runtime the host provides and record the interpreter in the evidence. It does not prove semantic correctness, safety, test coverage, or that a reviewer acted independently. Treat a structural pass as permission to continue review, never as approval to execute.

`scripts/snapshot_worktree.py` prints a reproducible `worktree-snapshot:<sha256>` revision over the workspace tree, for hosts or workspaces without a usable VCS revision.
