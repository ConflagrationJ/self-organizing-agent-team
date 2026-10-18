[English](README.md) | [中文](README.zh-CN.md)

# Self-Organizing Agent Team

An agent skill for governed self-organizing delivery: select the smallest team that the task risk justifies, enforce independent review, bind evidence to a revision, and stop before unauthorized external actions.

This is not an autonomous multi-agent framework. It is a coordination protocol. It does not replace the host's delegation, sandbox, approval, or tooling controls.

## Why it exists

Adding more agents can make a task slower and less reliable. The useful question is not "how many agents can run" but "what is the smallest team that adds independent evidence without adding uncontrolled write paths?"

The skill answers that with:

- risk-routing rubric;
- a hard cap of three subagents and two parallel agents;
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

Only the coordinator delegates. Writer and reviewer are different execution units; reviewers are read-only; write scopes are disjoint; high risk stops on revision drift, unauthorized actions, review-time writes, two unresolved rounds, or no measurable progress.

## Install

Copy this whole directory into a skill location read by the host.

Codex:

```text
$CODEX_HOME/skills/self-organizing-agent-team
```

Invocation policy: Codex reads `agents/openai.yaml`; implicit invocation is enabled so Codex can select the skill when the task genuinely needs governed multi-agent delivery. `$self-organizing-agent-team` remains available for explicit invocation.

Enable implicit routing only after independent forward tests.

## 30-second usage

1. Classify the task as low, medium, or high risk.
2. If low risk or delegation is unavailable, use one agent and an independent verification pass.
3. Otherwise copy `templates/task-contract.md`, set the task ID, base revision, write scope, gates, acceptance checks, and authorization requests.
4. Run `python scripts/validate_task_contract.py path/to/contract.md` as a structure check. Add `--manifest path/to/evidence-manifest.md` when handoff and acceptance files exist.
5. Run the gates in order: plan review (high risk only), implementation, code review, independent execution, acceptance.
6. Stop on revision drift, unauthorized action, review-time writes, two unresolved rounds, or no measurable progress.

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
| `scripts/validate_task_contract.py` | Structure-only validator |
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

The validator reads one fenced `json` block from a Markdown contract. It checks required fields, concrete execution-unit IDs, risk-to-team consistency, host-capability evidence shape, path shape, gate requirements, migration authorization, and evidence-binding flags.

With `--manifest`, it also checks the manifest's task ID and base revision against the contract, requires `reviewed_revision == executed_revision`, verifies the linked handoff, acceptance, host-evidence, and artifact SHA256 values against real files, and parses exact handoff/acceptance fields: handoff `state` must be `approved` or `executed`, and acceptance `Decision` must be `pass`. It does not prove the truth or authorship of those files.

It cannot determine whether the stated risk is correct, whether a reviewer was genuinely independent, whether a command actually ran, or whether the work is safe. Do not describe a passing result as semantic or behavioral validation.

`scripts/snapshot_worktree.py` prints a reproducible `worktree-snapshot:<sha256>` over the workspace tree, for hosts or workspaces without a usable VCS revision. The test suite creates its temporary directories under the current working directory instead of the OS temporary directory, because restricted sandboxes can deny access to `tempfile`-created directories.

## Compatibility and limits

- Delegation primitive names are not hard-coded. Detect what the host provides and record it.
- Host detection must include a method, observed result, evidence locator, timestamp, and a fallback record. When delegation is available, the fallback is recorded as available without being exercised.
- Without delegation, the skill degrades to one agent plus a fresh verification pass.
- Nested delegation is disabled by default.
- The default maximum is three subagents and two parallel subagents.
- Defaults, when a contract does not choose values, are 30 minutes per agent, 90 minutes total, and two no-progress rounds.
- This release does not claim production deployment experience, enterprise results, or autonomous operation.

## Publication boundary

The skill never commits, pushes, publishes, uploads data, changes permissions, installs system dependencies, or creates a release on its own. Each such action needs explicit user approval for the exact target and scope.

Do not place secrets, tokens, cookies, customer data, personal paths, or private datasets in a public repository.

## License

MIT. See `LICENSE`.
