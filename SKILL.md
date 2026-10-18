---
name: self-organizing-agent-team
description: Coordinate a risk-based, minimal multi-agent workflow with explicit ownership, write scopes, review gates, revision-bound evidence, and user authorization for external side effects. Use for multi-step delivery that spans code, data, or external operations; use the single-agent path when the task is low risk or delegation is unavailable.
---

# Self-Organizing Agent Team

Use this skill to choose the smallest safe team for a delivery task, not to create a team by default. Adapt to the host you actually have; do not require the user to change Codex configuration just to use this skill.

## Host compatibility preflight

Run the bundled preflight from the directory that contains this SKILL.md before spawning anyone:

```text
python <skill-dir>/scripts/host_preflight.py
```

It reads `config.toml`, the referenced model catalog, and the current session without changing configuration. It prefers the rollout named by `CODEX_THREAD_ID` / `CODEX_SESSION_ID`; `session_source` reports `current`, `latest`, or `explicit`. It mirrors the host runtime: a provider counts as OpenAI only when its configured provider name is exactly `OpenAI`; a base URL, including a local proxy URL, is not the test. Route on its `route` value:

- `v1`: the running session or effective config selects V1. Use the V1 surface and run the V1 probe.
- `v2_probe`: V2 is selected on the OpenAI provider. Run the V2 probe with `fork_turns: "none"`.
- `single_agent`: V2 is selected on a non-OpenAI provider (including a local proxy registered under a custom provider id), or multi-agent is disabled. Do not spawn in this turn. Record `delegation_available: false`, `detection.method: "host preflight"`, `detection.result: "unavailable"`, the measured route and reason, and run the single-agent path with a separate verification pass. Set `fallback.result: "exercised"` after that pass. If the user wants delegation, show the preflight's `repair_hint` (or the adapter's one-time repair) and get explicit approval before editing host configuration; expect a restart and a new chat.
- `restart_required`: the running session is V2 but the current config selects V1. Start a new chat, rerun the preflight, and only then decide.
- `probe`: the effective version cannot be determined. Run the probe.

If `config_mismatch` is true and the route is `v1`, the current session is still V1 while the config now selects V2. Use V1 for this session and restart after the current task if V2 is wanted.

`single_agent` is the default on a non-OpenAI V2 host. If the user explicitly asks to test whether a new host build has fixed the defect, run the preflight with `--probe`, then run the V2 probe. A passing probe is evidence for this host build only; do not treat it as a standing exception.

A host repair is optional and user-authorized, never a prerequisite. Keep it idempotent: back up the catalog first, change only the version field, verify with `codex debug models` and `codex features list`, then restart Codex and start a new chat. Existing threads keep their recorded version. Never touch provider credentials, game files, or saves as part of host repair. The skill must still work in single-agent mode when a restart is not possible.

## First: detect host capability

Tool discovery is not detection. A host can expose spawn, send, and follow-up primitives and still drop the task body: the child starts, reads the workspace, and answers with a greeting because it never received the task. Before any real delegation, run one round-trip probe from `templates/delegation-probe.md`:

1. Run the host compatibility preflight above. If it routes to `single_agent`, use the single-agent path; if it routes to `restart_required`, start a new chat and rerun it. If it routes to `v1` or `v2_probe`, pick two tokens and two workspace-relative paths (prefer `.sot-tmp/`, which the bundled `.gitignore` covers). Run the probe with history inheritance disabled: a host that copies the parent thread by default also copies the parent's spawn call, which carries TOKEN_A, and a fresh child can fake delivery from it. Use `fork_turns: "none"` on a V2 host and `fork_context: false` on a V1 host. If the host cannot disable inheritance, the probe is inconclusive and delegation is unavailable.
2. Spawn one disposable agent with TOKEN_A and FILE_A, requiring the lowercase sha256 of TOKEN_A in FILE_A, no trailing newline, and TOKEN_A in the reply. The file check is joint evidence for one round of delivery, execution, and write; do not split it into three independent conclusions. Attribute the stage from the reply, not the file: a greeting with no file fails delivery and write, while a permission error with no file means the task arrived and the write failed.
3. Send a follow-up that carries TOKEN_B and FILE_B only, requiring `TOKEN_A:TOKEN_B` in FILE_B and deletion of FILE_A. TOKEN_A is never written to the workspace, so a child that never saw the first task cannot produce FILE_B; that is what confirms the follow-up reached the same child. If a host creates a fresh child for the follow-up and hands it the parent thread, that child can read TOKEN_A from the transcript: history isolation is then unproven and the probe is inconclusive.
4. Record the six probe booleans, both tokens, both paths, the timestamp, and the raw log locator under `host_capabilities.detection.probe`, then delete FILE_B after recording its hash; the child already deleted FILE_A.

If any step fails, set `delegation_available: false`, use the single-agent path below, and record which step failed. A failed probe is evidence about the host, not a reason to repeat the same call until it looks successful. A preflight `single_agent` result is a known incompatibility, not a failed model call; do not spawn a disposable agent merely to reconfirm it.

A reply that never mentions the task - a greeting, "what do you want me to do", a summary of the workspace, an ignored token, or a reply quoting only the task header - means the task body did not arrive. That is a delivery failure, not a model refusal. A reply that does name the task and then refuses to write is a different case: delivery worked, and the write or policy gate failed. Record `initial_task_delivered: true` and `write_succeeded: false` for it.

Host policy, sandbox, and approval controls always take precedence over this protocol. Do not assume a particular tool name, syntax, or nesting model. If the host ships a documented adapter under `adapters/`, read it before creating anything. If no usable delegation mechanism exists:

1. Run the work as a single agent.
2. Perform a separate verification pass after implementation: reread the diff, run tests, and record evidence.
3. State explicitly that no subagents were created. Never imply that a team was formed.

Record the result in the task contract under `host_capabilities`, including the preflight route and reason, the probe result when one ran, evidence locator, timestamp, and a fallback record (`available`, or `exercised` after the single-agent pass actually ran). When the preflight routes to `single_agent`, set `detection.method: "host preflight"`, `detection.result: "unavailable"`, `detection.observed` to the measured route/version, plus `detection.evidence` and `detection.timestamp`, and omit `detection.probe`; the validator only requires the probe when `delegation_available` is true. A string such as `runtime-detected` is not evidence. The preflight and probe are entrance tickets for this host build only; rerun them after a host version, model, provider, or adapter change.

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

## Invocation management

When the user asks to change this skill's invocation mode, do not make them edit YAML manually. Run the bundled helper from the installed skill directory and verify the result:

```text
python scripts/set_invocation_mode.py --mode auto
python scripts/set_invocation_mode.py --mode explicit
python scripts/set_invocation_mode.py --check
```

- `auto` allows implicit selection for matching multi-agent delivery tasks.
- `explicit` requires `$self-organizing-agent-team`.
- Report the mode returned by `--check` and warn that a new chat may be required for skill metadata to reload.

## References

Read only what the current task needs:

- `references/role-catalog.md` for role permissions and handoff inputs.
- `references/scheduling-policy.md` for risk classification, dependency rules, budgets, states, and escalation.
- `references/evidence-and-gates.md` for evidence envelopes and review verdicts.
- `references/risk-and-authorization.md` for the external-action approval matrix.
Templates:

- `templates/delegation-probe.md`
- `templates/task-contract.md`
- `templates/evidence-manifest.md`
- `templates/handoff.md`
- `templates/plan-review.md`
- `templates/code-review.md`
- `templates/acceptance.md`

## Validation boundary

`scripts/validate_task_contract.py` checks structure and, when `--manifest` is supplied, linked-file hashes and revision equality. It needs Python 3.8 or newer; when the host does not expose `python` on `PATH`, use the runtime the host provides and record the interpreter in the evidence. It does not prove semantic correctness, safety, test coverage, or that a reviewer acted independently. Treat a structural pass as permission to continue review, never as approval to execute.

`scripts/snapshot_worktree.py` prints a reproducible `worktree-snapshot:<sha256>` revision over the workspace tree, for hosts or workspaces without a usable VCS revision.
