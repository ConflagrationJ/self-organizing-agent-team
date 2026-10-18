# Evidence and Gates

The purpose of evidence is to let an independent agent reproduce a claim or identify exactly why it cannot. A statement without revision, command, and artifact binding is not evidence.

## Evidence envelope

Each evidence item should use this shape:

```json
{
  "task_id": "TASK-2026-001",
  "base_rev": "worktree-snapshot:0123456789abcdef",
  "author": "agent-or-person-identifier",
  "artifact": "src/queue.py",
  "command": "python -m unittest tests.test_queue",
  "exit_code": 0,
  "timestamp": "2026-10-18T12:00:00Z",
  "scope": "queue retry tests",
  "artifact_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "artifact_locator": "optional equivalent locator when a hash is impractical",
  "raw_output": "exact command output or a stable log locator"
}
```

Requirements:

- `task_id` and `base_rev` must match the current contract.
- For a file claim, provide `artifact_sha256` or a precise locator; `file:line` without a revision is not sufficient.
- For a command claim, provide command, exit code, timestamp, and raw output or a stable locator.
- For a manual check, describe who checked what and attach a reproducible artifact when possible.
- Evidence from an older revision cannot approve a newer revision.

## Delegation probe evidence

Before the first delegated task, run the probe in `templates/delegation-probe.md` and record the result under `host_capabilities.detection.probe`.

The probe records six states. They are not six independent experiments:

- `history_isolated` says the child ran without the parent thread for the initial spawn and for any child the follow-up creates, so an inherited spawn call or transcript cannot supply the token;
- `same_child_confirmed` says the follow-up reached the child that wrote the first file, proven by a value that is not recoverable from the workspace. It holds only when `history_isolated` also holds; otherwise the value can come from the inherited transcript;
- `workspace_visible`, `initial_task_delivered`, and `write_succeeded` come from one round trip. The file check is joint evidence that delivery, execution, and write held together in that round. Do not report it as three independent conclusions, and do not reuse it for a later round. Delivery is attributed from the child's reply; the write is attributed from the file, so a greeting with no file fails both and a permission error with no file fails only the write;
- `followup_delivered` is the second round trip and carries its own artifact.

The evidence is the file the child wrote, read back by the coordinator, compared byte for byte after newline normalization, plus the reply that names the token. A spawn return value, an agent id, a task name, a nickname, or a child summary is not evidence.

It does not prove that later messages arrive, that a long prompt survives truncation, that a different child on the same host behaves the same way, or that any reviewer is independent. A passing probe is an entrance ticket for this host build.

Invalidate the probe when any of these occurs:

- the host build changes;
- the model or provider changes;
- the adapter or delegation configuration changes;
- the session restarts, or history inheritance is re-enabled;
- a real child answers with a generic greeting or a workspace summary, which means retest immediately rather than continue the task.

A failed probe is recorded, not deleted. Keep the measured values, name the failing stage, set `delegation_available: false`, and fall back to the single-agent path with a separate verification pass.

## Gate outputs

Every review gate returns exactly one verdict:

- `pass`: all required claims are supported, no unresolved high-severity issue remains.
- `conditional`: named conditions must be met before execution; the task remains blocked until they are evidenced.
- `fail`: at least one high-severity issue is unresolved or evidence is stale, missing, or contradictory.

Each finding includes:

- severity;
- trigger condition;
- consequence;
- counterexample or reproduction;
- required fix;
- evidence locator;
- status.

Do not write vague observations such as "consider improving this" without a decision.

## Plan review gate

Required for high-risk tasks before code changes.

The reviewer checks:

- data boundary and single source of truth;
- which constraints are hard versus weighted;
- interfaces and ownership between modules;
- concurrency, locks, idempotency, and ordering;
- permissions and authorization scope;
- deletion, network, publication, and other side effects;
- failure recovery and rollback;
- acceptance criteria and the minimum safe experiment;
- explicit unverified assumptions.

## Code review gate

Required for medium and high risk.

The reviewer receives the original contract, base revision, raw diff or files, and raw logs. The reviewer must:

- recompute at least one key claim;
- construct at least one counterexample relevant to the risk;
- check path boundaries and write scope;
- check secrets, PII, logging, and destination boundaries;
- check timeout, cancellation, late callbacks, empty inputs, duplicate execution, and partial failure where relevant;
- confirm that the reviewed revision is the execution candidate.

The reviewer does not modify files. A review-time write invalidates the review.

## Independent execution gate

Required for high risk.

The executor runs in an isolated workspace or with a documented equivalent isolation. Acceptance evidence must include:

- reviewed revision and executed revision;
- exact commands;
- exit codes;
- raw output or stable log locators;
- artifact hashes or locators;
- whether any external action was mocked, blocked, or approved;
- residual risk.

"Tests pass" without the above is not acceptance evidence.

## Evidence invalidation

Invalidate evidence when any of these occurs:

- the artifact hash changes;
- `base_rev` changes;
- the reviewed revision is not the executed revision;
- the command or environment changes materially;
- a reviewer writes to the workspace;
- the authorization target or scope changes.

Mark invalid evidence as stale. Do not delete it silently; preserve it for audit and request fresh evidence.

## Evidence manifest

Use `templates/evidence-manifest.md` to link the task contract to:

- the handoff file and its SHA256;
- the acceptance file and its SHA256;
- the host detection and fallback evidence files and their SHA256 values;
- artifact paths and SHA256 values;
- evidence envelopes for the executed revision.

The manifest requires `reviewed_revision == executed_revision`, `task_id` and `base_rev` equal to the contract, real files whose hashes match, exact parsed handoff fields (`task_id`, `reviewed_revision`, `state=approved|executed`), exact parsed acceptance fields (`task_id`, `executed_revision`, `decision=pass`), and host evidence for both detection and fallback. An old review revision or a failed acceptance therefore cannot pass the structure check.

This is still a structural and byte-hash check. It proves that the linked files exist and their bytes match the manifest; it does not prove who wrote them, whether the reviewer was independent, whether the recorded human action occurred, or whether raw output is truthful.

## Structural validator boundary

`scripts/validate_task_contract.py` verifies JSON structure and basic policy invariants only. It cannot prove that:

- the chosen risk level is correct;
- a review was independent;
- a command was executed;
- the linked file was produced by the named author or at the claimed time;
- the implementation is correct or secure.

Never turn a structural pass into a behavioral pass.
