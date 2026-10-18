[English](README.md) | [中文](README.zh-CN.md)

# Self-Organizing Agent Team

An agent skill for governed self-organizing delivery: select the smallest team that the task risk justifies, enforce independent review, bind evidence to a revision, and stop before unauthorized external actions.

This is not an autonomous multi-agent framework. It is a coordination protocol. It does not replace the host's delegation, sandbox, approval, or tooling controls.

## Why it exists

Adding more agents can make a task slower and less reliable. The useful question is not "how many agents can run" but "what is the smallest team that adds independent evidence without adding uncontrolled write paths?"

The skill answers that with:

- risk-routing rubric;
- a hard cap of three subagents, raised to six only for max-risk work, and two parallel agents;
- one coordinator with exclusive delegation authority;
- read-only reviewers and mutually exclusive write scopes;
- plan review before code for high-risk work;
- revision-bound evidence and invalidation on drift;
- explicit user approval for destructive, networked, published, or otherwise external actions.

## Core invariants and risk routing

This is a summary; `SKILL.md` and `references/` remain authoritative.

| Risk | Team | Required gates |
|---|---|---|
| Low | No subagent | Lead implements, rereads the diff, runs relevant tests, records evidence |
| Medium | Writer + independent reviewer | Code review, tests, revision-bound evidence |
| High | At most 3 subagents: writer, reviewer, executor | Plan review before writing, code review, independent execution, authorization |
| Max | At most 5 subagents (6 execution units including the coordinator): writer, reviewer, executor, optional second executor, acceptance reviewer | All high-risk gates plus result acceptance, with disjoint execution scopes |

Max is not a busier high-risk run: the second executor exists for parallel or sharded work, and the acceptance reviewer exists because code can pass every code gate while the numbers in the deliverable are wrong. Acceptance review and plan review are different execution units.

Only the coordinator delegates. Writer and reviewer are different execution units; reviewers are read-only; write scopes are disjoint; high and max risk stop on revision drift, unauthorized actions, review-time writes, two unresolved rounds, or no measurable progress.

## Install

Copy this whole directory into a skill location read by the host.

Codex:

```text
$CODEX_HOME/skills/self-organizing-agent-team
```

Invocation policy: Codex reads `agents/openai.yaml`; implicit invocation is enabled so Codex can select the skill when the task genuinely needs governed multi-agent delivery. `$self-organizing-agent-team` remains available for explicit invocation.

Enable implicit routing only after independent forward tests.

### Invocation mode / 调用模式

Default is `auto`. You do not need to edit YAML. Ask the agent in either language:

- "Set self-organizing-agent-team to automatic invocation."  
  “把 self-organizing-agent-team 设为自动调用”
- "Set self-organizing-agent-team to explicit invocation."  
  “把 self-organizing-agent-team 改成仅显式调用”
- "Check the current invocation mode for self-organizing-agent-team."  
  “检查 self-organizing-agent-team 当前调用模式”

The agent runs `scripts/set_invocation_mode.py` and reports the result. A new chat may be needed before the new metadata is loaded.

## 30-second usage

1. Run `python <skill-dir>/scripts/host_preflight.py` to read the current host route without changing configuration.
2. Run the delegation probe from `templates/delegation-probe.md` before the first delegated task, with history inheritance disabled. Record both tokens, both paths, and the six probe states in the contract.
3. Classify the task as low, medium, high, or max risk.
4. If low risk, `single_agent` from preflight, or the probe failed, use one agent and an independent verification pass.
5. Otherwise copy `templates/task-contract.md`, set the task ID, base revision, write scope, gates, acceptance checks, and authorization requests.
6. Run `python scripts/validate_task_contract.py path/to/contract.md` as a structure check. Add `--manifest path/to/evidence-manifest.md` when handoff and acceptance files exist.
7. Run the gates in order: plan review (high and max risk), implementation, code review, independent execution, result acceptance (max risk), acceptance.
8. Stop on revision drift, unauthorized action, review-time writes, two unresolved rounds, or no measurable progress.

## Forward-test acceptance scenarios (not executed)

These are acceptance scenarios, not claims of completed behavioral evaluation. `scripts/test_forward_scenarios.py` only checks that the low-risk contract has no team and the high-risk contract has the required gates; it is a structural fixture, not a live agent test. As of 2026-10-18 the structural fixture suite and the validator test suite pass; no live-agent forward test has been run.

```text
python scripts/test_forward_scenarios.py
```

### Low risk: one CLI flag

Request: add `--dry-run` to a small local CLI, update its tests, and run them.

Expected behavior:

- no plan red team and no multi-agent ceremony;
- zero subagents;
- changes limited to the CLI and its tests;
- test command, exit code, and output are recorded;
- no team is declared if the main agent performs the work directly.

Failure: opening any subagent, creating a handoff ceremony, or changing unrelated files.

### High risk: idempotent retry with an external side effect

Request: add retry-safe idempotent submission to a local queue, call a mock webhook after success, and remove expired temporary files.

Expected behavior:

- task contract identifies concurrency, idempotency, deletion, network, and external side effects;
- an independent reviewer examines duplicate send, crash-after-write, lock expiry, clock skew, retry storm, and cleanup boundaries before code is written;
- writer and reviewer are different execution units;
- the mock webhook and deletion target require explicit user approval;
- code review constructs at least one failure counterexample;
- a separate executor runs tests in an isolated workspace;
- acceptance binds the tested revision, command, exit code, timestamp, and artifact hash;
- work stops after two unresolved review rounds instead of looping.

Failure: writing code before plan review, reviewing your own change, modifying files during review, calling a real external service without approval, or reporting "tests pass" without reproducible evidence.

## Files

| Path | Purpose |
|---|---|
| `SKILL.md` | Entrypoint, routing, invariants, and gate order |
| `references/role-catalog.md` | Role permissions and inputs |
| `references/scheduling-policy.md` | Risk, dependency, concurrency, budget, and stop rules |
| `references/evidence-and-gates.md` | Evidence envelope and review verdicts |
| `references/risk-and-authorization.md` | Approval matrix for external and irreversible actions |
| `templates/` | Contract, handoff, review, and acceptance forms |
| `templates/delegation-probe.md` | History-isolated round-trip delivery probe for the host delegation tools |
| `adapters/` | Host-specific notes, including known delegation defects |
| `scripts/validate_task_contract.py` | Structure-only validator |
| `scripts/host_preflight.py` | Read the local Codex host and return `v1`, `v2_probe`, `single_agent`, `restart_required`, or `probe` without changing configuration |
| `scripts/set_invocation_mode.py` | Switch `auto` / `explicit` invocation policy in `agents/openai.yaml` |
| `scripts/snapshot_worktree.py` | Reproducible `worktree-snapshot:<sha256>` revision for workspaces without a VCS revision |
| `scripts/test_validate_task_contract.py` | Positive, negative, and manifest validator tests |
| `scripts/test_forward_scenarios.py` | Structural fixture check for the two forward scenarios |

## Composing with other skills

This skill governs coordination, not domain method, so it is meant to stack with task-specific skills:

- Load the domain skills first; this protocol decides who acts and what counts as evidence, not how to do the domain work.
- Do not let a teammate's skill choice weaken a gate. A reviewer that loads a "be pragmatic" skill still owes raw inputs, an independent recomputation, and a verdict.
- Host policy and tool schemas win over this skill. When they conflict, follow the host and record the exception.
- Load this skill in the Lead's context. Teammates run in the shared working directory and can read the protocol file, and a member may be able to load the skill too; do not rely on either — put the task package and the protocol path in each spawn prompt.

## Structure validator

```text
python scripts/validate_task_contract.py templates/task-contract.md
python scripts/validate_task_contract.py path/to/contract.md --manifest path/to/evidence-manifest.md
```

The validator reads one fenced `json` block from a Markdown contract. It checks required fields, concrete execution-unit IDs, risk-to-team consistency, host-capability evidence shape, delegation probe completeness when delegation is available, path shape, gate requirements, migration authorization, and evidence-binding flags.

With `--manifest`, it also checks the manifest's task ID and base revision against the contract, requires `reviewed_revision == executed_revision`, verifies the linked handoff, acceptance, host-evidence, and artifact SHA256 values against real files, and parses exact handoff/acceptance fields: handoff `state` must be `approved` or `executed`, and acceptance `Decision` must be `pass`. It does not prove the truth or authorship of those files.

It cannot determine whether the stated risk is correct, whether a reviewer was genuinely independent, whether a command actually ran, or whether the work is safe. Do not describe a passing result as semantic or behavioral validation.

`scripts/snapshot_worktree.py` prints a reproducible `worktree-snapshot:<sha256>` over the workspace tree, for hosts or workspaces without a usable VCS revision. The test suite creates its temporary directories under the current working directory instead of the OS temporary directory, because restricted sandboxes can deny access to `tempfile`-created directories.

## Compatibility and limits

- Delegation primitive names are not hard-coded. Detect what the host provides and record it.
- Host detection must be a round-trip probe with history inheritance disabled: a disposable child writes the digest of a unique token to a workspace-relative file, the coordinator reads it back, then a second token goes through the follow-up channel and must prove it reached the same child. All six probe states must be true, tokens and paths must differ, and any failure means the single-agent path.
- The fallback record stays `available` when delegation passes the probe. Record `exercised` only after the single-agent verification pass actually ran.
- Without delegation, the skill degrades to one agent plus a fresh verification pass.
- Nested delegation is disabled by default.
- The default maximum is three subagents and two parallel subagents; max-risk work may raise the subagent total to six but not the parallel count.
- Defaults, when a contract does not choose values, are 30 minutes per agent, 90 minutes total, and two no-progress rounds.
- This release does not claim production deployment experience, enterprise results, or autonomous operation.

### Migration

This release tightens validation on purpose. A contract with `delegation_available: true` and no `detection.probe` now fails validation. An existing contract must either record a probe result or set `delegation_available: false`, `detection.result: "unavailable"`, `fallback.result: "exercised"`, and turn every delegated gate off. `contract_version` stays 1; no version bump accompanies this change.

## Known host issues

- Codex MultiAgentV2 on a non-OpenAI provider encodes plaintext tasks as encrypted messages: the child starts, reads the workspace, and answers with a greeting. See `adapters/codex-multi-agent-v2/README.md` for tool signatures and source references.
- `scripts/host_preflight.py` recognizes the `V2 + non-OpenAI provider` combination and returns `single_agent`. This includes a local proxy registered under a custom provider id; the runtime test is the resolved provider name (`OpenAI`), not the base URL. The skill finishes the current task with the single-agent path and a fresh verification pass; it does not edit Codex configuration by itself. The preflight reports `repair_needed` and a `repair_hint` when a one-time host repair is available.
- If the user explicitly wants delegation, offer the one-time repair from the adapter: quit cc-switch if it generates the catalog (disable its auto-start if it launches with Codex or Windows), back up the catalog, set the selected model's `multi_agent_version` to `v1`, verify with `codex debug models` and `codex features list`, restart Codex, and start a new chat. Existing threads keep their recorded version. The repair is optional and never a prerequisite.
- The preflight prefers the rollout named by `CODEX_THREAD_ID` / `CODEX_SESSION_ID`, so a still-running old thread does not force `restart_required`.

## Publication boundary

The skill never commits, pushes, publishes, uploads data, changes permissions, installs system dependencies, or creates a release on its own. Each such action needs explicit user approval for the exact target and scope.

Do not place secrets, tokens, cookies, customer data, personal paths, or private datasets in a public repository.

## License

MIT. See `LICENSE`.
