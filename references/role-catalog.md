# Role Catalog

The role catalog defines permissions, not job titles. Assign only the roles needed by the risk tier.

## Coordinator

Owner: the main agent or main thread.

- May create, send work to, wait for, and close subagents.
- Owns the task contract, risk classification, write-scope partition, budgets, and final acceptance.
- Must not fabricate evidence for a subagent.
- Must not let two agents write the same artifact concurrently.
- Must stop the task on unauthorized side effects, review-time writes, revision drift, or two unresolved rounds.

## Independent reviewer

Also used as the plan red team when plan review is required.

- Default access: read-only.
- Inputs: original task contract, base revision, raw diff or files, raw command output, and acceptance criteria.
- Must not see the writer's interpretation or claimed conclusion before forming an initial finding.
- Must independently recompute at least one key piece of evidence.
- Must construct at least one concrete counterexample or failure scenario for high-risk work.
- Must give severity, trigger condition, consequence, required fix, and a verdict.
- A plan reviewer may later review code, but remains a different execution unit from the writer.

Use the same reviewer for plan and code review in the default high-risk team. This keeps the team within the three-subagent cap while preserving author-reviewer separation.

## Writer

- May modify only paths listed in `write_scope`.
- May not create or close subagents.
- May not approve its own work.
- Must return file and line references, commands attempted, and unresolved questions.
- Must stop before an external side effect not listed in the contract and approved by the user.
- Task assignments must use concrete execution-unit IDs, never `TBD` or another placeholder.

## Executor

- Runs only a reviewed revision and only the commands or probes allowed by the task contract.
- May not fix code, widen scope, or reinterpret acceptance criteria.
- Must record command, exit code, timestamp, raw output, artifact hash or locator, and tested revision.
- Must stop on revision drift, unauthorized network access, missing approval, or a failed prerequisite.
- Must be a different execution unit from both writer and reviewer.

## Optional analyst

- Default access: read-only.
- May produce a report only when the report path is explicitly included in `write_scope`.
- Must provide a reproducible calculation or source locator for quantitative claims.
- Must not be both analyst and independent verifier of the same result.

## Optional monitor

- Default access: read-only.
- Watches heartbeats, process liveness, files, limits, or risk signals.
- Reports observations and evidence. Does not decide semantic correctness or approve execution.

## Handoff rules

- One task uses one handoff file named from its `task_id`; do not let multiple agents overwrite a shared handoff.
- Reviewers receive raw inputs and evidence, not a compressed author narrative.
- Any write by a read-only role invalidates that role's review.
- The coordinator checks the artifact revision before and after review. If it changed, the review is stale.
- Subagents do not create subagents by default. Only the coordinator may change that rule with explicit user permission.
