# Scheduling Policy

## Host capability detection

Public skills must not assume a specific delegation API. Inspect the current host for any mechanism that can create, message, wait for, and close an independent execution unit.

Record one of these outcomes in the task contract:

- `delegation_available: true` with a `detection` record containing method, observed result, evidence locator, timestamp, `result=available`, and a `probe` block from `templates/delegation-probe.md` whose six states are true, including `history_isolated` and `same_child_confirmed`, with distinct tokens, distinct paths, and its own evidence locator and timestamp;
- `delegation_available: false` with `detection.result=unavailable` and `fallback.result=exercised`;
- always include a `fallback` record with method, observed result, evidence locator, timestamp, and result.

Evidence locators must point to an actual probe, log, or command output. `runtime-detected`, `TBD`, and similar strings are rejected by the structural validator.

If delegation is unavailable, do not simulate a team. The main agent performs the work, then performs a separate verification pass.

## Risk classification

Use the first matching tier and choose the higher tier when uncertain.

### Low

All of the following are true:

- one local file or one narrow test surface;
- no shared interface or schema;
- reversible change;
- no network, deletion, permissions, secrets, migration, publication, payment, or production action;
- existing tests or a clear local check cover the behavior.

Routing: one agent, no subagents.

### Medium

Any of the following is true, without high-risk flags:

- two or more related files or modules;
- a shared internal interface;
- moderate regression surface;
- a data transformation that is reversible with a local backup;
- a review adds meaningful independent evidence.

Routing: at most two subagents: writer and independent reviewer.

### High

Any of the following is true:

- concurrency, locks, retries, timers, or ordering constraints;
- authentication, authorization, permissions, or identity;
- secrets, PII, private datasets, or data exfiltration risk;
- schema or state migration;
- local delete or overwrite beyond a disposable fixture;
- network, third-party API, webhook, CI, release, publication, payment, or production;
- irreversible action or broad blast radius.

Routing: at most three subagents: writer, independent reviewer, executor. The reviewer performs plan review before implementation and code review after implementation.

### Max

Any of the following is true:

- the deliverable is irreversible or externally delivered, and it carries both code and conclusions or data;
- the work needs parallel or sharded execution to fit its budget;
- the result needs independent acceptance because a correct execution can still produce a wrong conclusion;
- a prior High-risk run passed every code gate and still shipped a wrong number or an unsupported claim.

Routing: at most five subagents (six execution units including the coordinator): writer, reviewer, executor, optional second executor, acceptance reviewer. The reviewer performs plan review before implementation and code review after implementation; the acceptance reviewer judges the result separately and is never the same execution unit as the reviewer, the writer, or either executor.

Max is not a busier High. Add the second executor only for parallel or sharded work; add the acceptance reviewer only when the deliverable makes a claim that execution evidence cannot settle. A Max task without either condition is still a High task.

On a host where delegation is unavailable, Max cannot be expressed: `delegation_available: false` requires `single_agent`, while Max requires `max_gate`. Downgrade the task to High and record the fallback explicitly; do not silently drop the acceptance reviewer while keeping the Max label.

## Dependency and concurrency rules

- Build a lightweight dependency graph before delegating.
- Independent read-only work may run in parallel.
- Writes that share a path must be serialized.
- Reviewer work depends on a frozen implementation revision.
- Execution depends on an approved code review.
- Default maximum: three subagents total and two running in parallel; a Max task may raise the total to five subagents (six execution units including the coordinator) but never the parallel count to more than two.
- No unbounded fan-out and no recursive delegation by subagents.

## Write-scope rules

- Paths are project-relative and normalize inside the project root.
- Reject absolute paths, drive-qualified paths, home-directory shorthand, NUL bytes, and `..` traversal.
- Give each writer a disjoint path set.
- Reviewers and monitors have an empty write scope unless the user explicitly changes their role.
- Any write outside `write_scope` stops the task.

## Default budgets

Use the contract values when present. Otherwise:

- 30 minutes per subagent;
- 90 minutes total;
- two no-progress rounds;
- two writer-reviewer rounds maximum;
- two parallel subagents maximum.

These are defaults, not permission to run longer or spend more.

## No-progress detection

Count a round as no progress when any of these is true:

- no new artifact or evidence;
- only a repeated conclusion;
- the same blocker without a changed plan;
- a pending subagent exceeds its timeout;
- evidence cannot be tied to the current revision.

Stop on two consecutive no-progress rounds.

## State machine

Allowed handoff states:

```text
draft
  -> ready_for_review
  -> changes_requested | approved
  -> executed | aborted
```

Rules:

- Do not skip states.
- `approved` binds to a specific reviewed revision.
- Any artifact change after approval moves the task back to `ready_for_review`.
- `executed` requires acceptance evidence for the approved revision.
- A stale or abandoned handoff is marked `aborted`; it is not silently reused.

## Escalation

After two unresolved writer-reviewer rounds, or a budget breach, stop and choose exactly one:

1. split the task;
2. replace the plan;
3. reduce scope;
4. ask the user.

Do not add a third review round or more agents to force a pass.

## Cancellation

Only the coordinator closes subagents. Before closing, record:

- task ID;
- last state;
- revision;
- reason for stopping;
- artifacts produced;
- unresolved questions;
- whether any external action occurred.
