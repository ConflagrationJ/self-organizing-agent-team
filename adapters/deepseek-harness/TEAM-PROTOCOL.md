# DSH Team Protocol

This is the Lead-facing protocol for DeepSeek Harness (DSH) Agent Teams. It adapts the skill's governed team model to DSH's real tools and limits.

It is not a DSH plugin, not an official certification, and not a promise of stable schemas. Read the main skill's `references/` files when working from the full repository. DSH's own Team policy, approval flow, and sandbox remain authoritative; this protocol only adds risk routing and gates.

Checked against DSH Desktop 44.7.0, profile `desktop`, on 2026-10-18.

## 1. Authority and roles

| Governance role | DSH identity | Responsibility |
|---|---|---|
| Coordinator | `lead` | Risk routing, task graph, ownership, authorization, final acceptance |
| Writer | named teammate | Implements only assigned write scopes |
| Reviewer | named teammate | Plan red team and code review; read-only by protocol |
| Executor | named teammate | Runs the reviewed revision and records evidence |
| Analyst | named teammate, optional | Reproducible analysis only |
| Monitor | named teammate, optional | Observations and risk signals only |

- Only the Lead may call `spawn_teammate` and `interrupt_agent`; DSH enforces this at execution time.
- Do not create a nested team. A teammate calling `subagent`, `subagent_fork`, or any other delegation tool is a stop condition.
- The Lead must not be the writer, reviewer, or executor. The Lead does coordinate, read the final diff, rerun the final checks, and make the acceptance decision.
- Any member may message any other member and use the task board. Peer messages do not replace task ownership, review independence, or Lead acceptance.
- All members receive the same nine tools; Lead-only operations fail when a teammate calls them. State the rule in every spawn prompt anyway.

## 2. Preconditions and mechanism choice

1. Confirm the composition: call `list_agents`; a mounted Team service returns the Lead row. Then confirm `spawn_teammate`, `send_message`, `team_task_create`, `team_task_get`, `team_task_list`, `team_task_update`, `wait_agent`, and (if enabled) `interrupt_agent`.
2. If the Team tools are missing, do not simulate a team. Use the Lead-only path, record the probe output, and state that no team was created.
3. If both Team tools and `subagent` / `subagent_fork` are visible, use only the Team tools. A `subagent` child is not a team member: it has no `target`, cannot own a task, and cannot satisfy a gate.
4. Record the mechanism in `host_capabilities.adapter` as `dsh-agent-team-v1`, with the probe output as `detection.evidence`.
5. A mounted service is a precondition, not delivery evidence. After the first spawn, spend one message on the nonce round trip in section 7 and record the result under `host_capabilities.detection.probe`.

## 3. Risk routing and team shape

Choose the higher tier when evidence is mixed.

| Risk | Team | Required gates |
|---|---|---|
| Low | No teammate. Lead implements, rereads the diff, runs tests, records evidence. | Scope check, relevant tests, evidence |
| Medium | 1 writer + 1 reviewer | Independent code review, tests |
| High | 3 teammates: writer, reviewer, executor (adapter policy cap) | Plan review before writing, code review, independent execution, authorization |

- The adapter cap is three teammates. DSH's shipped Desktop profile allows `maxMembers: 8`; the package default is `16`. The tighter policy wins.
- Do not add an analyst or monitor to the default high-risk team. Add an optional role only when it replaces a required role or the user explicitly accepts a different team shape.
- The same reviewer may do plan review and code review. That keeps the cap while preserving writer-reviewer separation.
- The `spawn_teammate` tool has no model parameter, so per-role model selection is not part of the tool surface. Do not promise a different model per role; set the model at the composition level if needed.
- Set `team.max_agents` to `0` (low), `2` (medium), or `3` (high). Set `team.max_parallel` to at most `2`; DSH has no parallel limit, so the Lead enforces it by serializing work through `blocked_by` and by messaging only one writer at a time.

## 4. Boot sequence

1. Classify risk and choose teammate names (lower-kebab-case, unique, permanent).
2. Create the board tasks with `team_task_create`, including `blocked_by` and `write_scopes`.
3. Write the task contract using the returned board ids as `task_id` and the chosen names as `team.assignments`.
4. Spawn only the needed teammates with `spawn_teammate`, using `context: fresh`.
5. Send each teammate its package: task id, board task id, base snapshot, write scope, inputs, gates, stop conditions, and the path of this protocol.
6. Before every `team_task_update`, call `team_task_get` and pass the current `expected_revision`.
7. Use `wait_agent` plus `team_task_list` / `list_agents` to observe; always re-read state after a wait.
8. Review the final diff, recompute the snapshot, and run the final tests yourself before accepting.

High-risk dependency chain:

```text
plan-review task
  -> writer task
  -> code-review task
  -> executor task
  -> Lead acceptance
```

The writer must not claim the writer task before plan review completes. The executor must not claim the executor task before code review is approved. `blocked_by` encodes this; DSH refuses a claim on an unready task.

A `fresh` teammate knows only its system policy, its initial prompt, and files it reads. `spawn_teammate` delivers the prompt unchanged; it is the whole initial task. Do not assume the teammate read the protocol because the Lead did.

The first spawn is also the only leg with a delivery guarantee: `spawn_teammate` validates persistent acceptance of the initial prompt before the member goes `active`, and raises `TEAM_PROVISIONING_CONFLICT` if that fails. `send_message` has no equivalent guarantee, so run one nonce round trip after the first package and before relying on any follow-up: the member writes the nonce to `.sot-tmp/probe-<nonce>.txt`, and the Lead hashes the file. One message is the whole cost.

## 5. Task-board discipline

- Use `team_task_create` for every unit of work. New tasks are unowned and pending; DSH assigns ids such as `task-1`.
- Put the human-readable label in `subject`; keep `task_id` in the contract equal to the board id.
- `write_scopes` are workspace-relative prefixes. DSH warns when two in-progress tasks plan overlapping paths and never blocks a write; treat the warning as a planning error.
- Claim only when every `blocked_by` task is complete. Read the task with `team_task_get` first; mutate with `expected_revision`.
- `claim` when starting; `release` when abandoning without completion; `complete` only after evidence is attached; `reopen` when the reviewed revision changes; `reassign` only when the Lead decides ownership must move; `edit` only to clarify scope; `set_dependencies` only after rechecking the DAG; `delete` only for an obsolete task.
- `delete` is a tombstone: it is not a completion state and the task disappears from the active board.
- If DSH reports `TEAM_TASK_STALE_REVISION`, reread with `team_task_get`, recompute the change, and retry once. If it repeats, stop and report it.
- If the board reports `TEAM_TASK_LIMIT`, prune obsolete tasks (only ones that are not evidence) or reduce scope; do not delete evidence.
- Owner never releases automatically because a teammate becomes `inactive`, is interrupted, exits, or fails. The Lead must reassign, release, or complete explicitly.

## 6. Review independence and gates

Reviewer inputs, delivered before any writer conclusion:

- the original task contract;
- the base snapshot and the frozen reviewed revision;
- the raw diff or the changed files;
- raw command output;
- the acceptance criteria.

DSH gives every member the same tools; there is no read-only mode. Reviewer read-only is a protocol rule enforced by the Lead:

1. Compute the snapshot (see section 8) before the reviewer starts.
2. Tell the reviewer to read only and to report findings.
3. Recompute the snapshot after the review. Any change invalidates the review: re-freeze the revision and obtain a new review.
4. Record both snapshot values and the check command in the review document.

For high risk, plan review checks data boundaries, interface ownership, concurrency, locks, idempotency, permissions, external effects, failure recovery, acceptance criteria, and unverified assumptions before the writer starts.

For medium and high risk, code review checks the exact reviewed revision, path boundaries, secrets/PII, empty input, timeout, cancellation, duplicate execution, partial failure, and rollback.

Use at most two writer-reviewer rounds. On the second unresolved round, stop and escalate. Do not add a third round or more teammates to force a pass.

## 7. Messages, waiting, and interruption

- `spawn_teammate` validates persistent acceptance of the initial prompt before the member goes `active`; a delivery failure raises `TEAM_PROVISIONING_CONFLICT`. `send_message` success means inbox acceptance only: DSH does not retry, deduplicate, or confirm processing.
- A successful spawn proves the initial prompt was persisted, not that the member acted on it. To prove a body arrived and was acted on, spend one message: send a nonce, require the member to write it to `.sot-tmp/probe-<nonce>.txt`, and hash the file yourself. A `list_agents` row is not delivery evidence.
- One message is capped at 64 KiB. Send paths, hashes, and short excerpts; put full diffs and logs in workspace files.
- Any member may message any other member; self-messaging is rejected.
- `wait_agent` waits for the next roster, task, message-acceptance, or live-status change. It reports only change or timeout (10 s to 1 h). It returns `noProgress` immediately when no other member is running or provisioning; that means wake someone with a message, not that work failed.
- `inactive` means no turn is executing. A teammate normally goes `inactive` after finishing a turn and can be cold-resumed by a message. It does not mean success, failure, or completion.
- `provisioning` and `failed` describe member creation. A `failed` creation is terminal for that name and consumes capacity.
- `interrupt_agent` cancels only the current turn, keeps the inbox, and does not release task ownership. Use it for a runaway turn, not as a cancel-and-cleanup operation.

## 8. Evidence envelope and revision binding

Each evidence item:

```json
{
  "task_id": "task-1",
  "base_rev": "worktree-snapshot:<64 hex characters>",
  "author": "executor",
  "artifact": "relative/path",
  "command": "exact command",
  "exit_code": 0,
  "timestamp": "2026-10-18T12:00:00Z",
  "scope": "what the evidence covers",
  "artifact_sha256": "64 hex characters or empty",
  "artifact_locator": "stable locator when hashing is impractical",
  "raw_output": "exact output or stable log locator"
}
```

Compute `base_rev` reproducibly:

- Git project: `git rev-parse HEAD` plus a working-tree hash, recorded with the exact command and output; or
- no VCS: `python scripts/snapshot_worktree.py .` from the bundle, which prints `worktree-snapshot:<sha256>` over sorted relative paths and file bytes.

Freeze the snapshot before the reviewer starts. Evidence from an older revision cannot approve a newer revision; a changed snapshot after review invalidates that review. DSH computes none of this for you: the executor or Lead records it, and the Lead reruns or verifies the final check. A teammate's "tests pass" is not acceptance evidence.

## 9. External effects and authorization

Ask for explicit user approval before any concrete external or irreversible action:

- local delete or overwrite beyond a disposable fixture;
- Git history changes;
- secrets or PII access;
- network, third-party APIs, webhooks, uploads, or scraping;
- dependency installation;
- CI, release, publication, or package registry changes;
- permissions or identity changes;
- payments or financial actions;
- production, migration, bulk data change, or destructive cleanup.

Approval must name the action, target, scope, reversibility, rollback, and any expiry. Approval does not carry across tasks, revisions, payloads, or targets. A DSH sandbox permission is not user intent: the sandbox may allow a command that still needs approval. If the scope changes, stop and ask again.

## 10. Stop and escalation rules

Stop immediately when:

- an external action lacks explicit approval;
- a reviewer writes during review, or the post-review snapshot differs;
- the reviewed revision differs from the executed revision;
- the same blocker repeats for two rounds without new evidence;
- the task board reports repeated stale revisions;
- a teammate's creation is `failed`, or a Lead-declared required member cannot be created;
- a teammate spawns a nested child (`subagent` / `subagent_fork`);
- the Lead cannot inspect the final diff or run the final test;
- the user changes scope or revokes authorization.

Do not stop merely because a teammate is `inactive` and no member is running: that is the normal state between turns and after a completed turn. Wake the member that owes the next action, or take the next Lead step. Stop only when the member is `failed`, when a required wake-up produces no progress after two rounds, or when a task is blocked without an owner.

After two unresolved writer-reviewer rounds, choose one: split the task, replan, reduce scope, or ask the user. Do not silently widen the team.

## 11. Budgets and timeouts

The contract's budget is policy; DSH has no per-agent timer.

- Defaults when the contract omits values: 30 minutes per teammate, 90 minutes total, two no-progress rounds, two writer-reviewer rounds, two parallel teammates.
- Implement a per-teammate budget by looping `wait_agent` with a bounded timeout and checking elapsed time. `wait_agent` accepts 10 s to 1 h.
- On budget expiry, `interrupt_agent` the runaway turn (if registered), record the last state, and escalate rather than silently extending.
- Count a round as no progress when there is no new artifact or evidence, only a repeated conclusion, the same blocker without a changed plan, a member over budget without a result, or evidence that cannot be tied to the current revision.

## 12. DSH limits that must remain visible

- One process and one shared working directory. No worktree isolation, merge step, or file lock.
- `write_scopes` are warnings. Bash, formatters, generators, and direct writes can bypass ownership; the Lead inspects the final diff.
- No per-member read-only permissions. Reviewer read-only is a Lead-enforced protocol rule backed by snapshot comparison.
- `send_message` success is inbox acceptance, not processing; no retry or deduplication. A successful spawn proves persistence of the initial prompt, not execution.
- `inactive` is not done, failed, or complete; task owners are never released automatically.
- `interrupt_agent` cancels a turn only, keeps the inbox, and does not release ownership; it is optional across compositions.
- Team packages are experimental and carry no stability promise.
- `maxMembers` counts failed creations; names are never reused or deleted.
- Large messages are rejected or must be split; keep evidence in files.
- The Lead must check the final diff and run the final tests. Team status or a writer summary is not acceptance evidence.
