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

## Secondary executor

Used on Max tasks that need parallel or sharded execution.

- Same permissions and the same prohibitions as the executor.
- Must hold a write scope and a run scope that are disjoint from the primary executor's; neither may write the same artifact or run the same destructive probe. This exclusion is not structurally validated by the contract; the coordinator must confirm disjoint scopes before dispatch.
- Must record command, exit code, timestamp, raw output, artifact hash or locator, and tested revision for its own shard only.
- Must be a different execution unit from the primary executor, the writer, the reviewer, and the acceptance reviewer.
- A conflict between the two executors is resolved by the coordinator, not by one executor overwriting the other's shard.

## Optional analyst

- Default access: read-only.
- May produce a report only when the report path is explicitly included in `write_scope`.
- Must provide a reproducible calculation or source locator for quantitative claims.
- Must not be both analyst and independent verifier of the same result.

## Optional monitor

- Default access: read-only.
- Watches heartbeats, process liveness, files, limits, or risk signals.
- Reports observations and evidence. Does not decide semantic correctness or approve execution.

## Acceptance reviewer

Used on Max tasks. Also called the result reviewer.

- Default access: read-only.
- Inputs: the original acceptance criteria, the delivered artifacts, and the raw data, logs, or export behind every quantitative claim.
- Must not receive the writer's or the executor's summary as the primary input. The raw outputs come first.
- Must return two separate verdicts, never one blended verdict:
  - **execution correctness**: was the reviewed revision the executed revision, did the stated commands run, do the hashes and locators match;
  - **conclusion validity**: does the deliverable say what the evidence supports.
- For conclusion validity it must check, at minimum:
  - caliber consistency: numerator and denominator cover the same population, filter, and snapshot time;
  - sample bias: a subgroup with too few or non-random samples cannot carry a conclusion;
  - confounding: a cross-group difference must control for composition before it is reported as an effect;
  - claim span: a mention rate is not a requirement, a successful call is not a valid result, a passing test is not a correct decision.
- Must independently recompute at least one key number from the raw data.
- Must give severity, trigger condition, consequence, required fix, and a verdict of `pass`, `conditional`, or `fail`.
- Must be a different execution unit from the writer, the reviewer, and both executors. A review-time write invalidates the review.

## Handoff rules

- One task uses one handoff file named from its `task_id`; do not let multiple agents overwrite a shared handoff.
- Reviewers receive raw inputs and evidence, not a compressed author narrative.
- Any write by a read-only role invalidates that role's review.
- The coordinator checks the artifact revision before and after review. If it changed, the review is stale.
- Subagents do not create subagents by default. Only the coordinator may change that rule with explicit user permission.
