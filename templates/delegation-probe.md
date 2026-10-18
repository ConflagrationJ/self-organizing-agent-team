# Delegation Probe

Run this probe before the first real delegation on a host, and rerun it after any host build, model, provider, or adapter change. Copy the result into `host_capabilities.detection.probe` in `templates/task-contract.md`.

## Purpose

A host can expose spawn, send, and follow-up tools and still fail to deliver the task body. The child process starts, reads the workspace, and answers with a greeting because it never received the task. Tool discovery cannot detect this. Only an artifact written by the child proves that the task arrived.

A host can also copy the parent thread into the child. The parent's spawn call contains the probe tokens, so an inherited history makes a child that never received the task look like it did. The probe therefore runs with history inheritance disabled, and it proves that the follow-up reached the same child, not merely that some child exists.

## Hard requirements

- Disable history inheritance for the initial spawn and for any child the follow-up creates: `fork_turns: "none"` on a V2 host, `fork_context: false` on a V1 host. Never run the probe with `fork_turns: "all"`; V2 defaults to `all`, and inherited spawn arguments make the probe pass without any delivery.
- If the host cannot disable inheritance, the probe is inconclusive. Record `delegation_available: false`; do not read a written file as success.
- While the probe runs, no workspace file may contain a full token except FILE_B, which is the recall test. FILE_A holds only the lowercase sha256 of TOKEN_A, so a different child that can list the workspace gains nothing from reading it. Delete FILE_B after verification, then record the tokens in the contract.
- Keep the follow-up on the same child. TOKEN_A is never written to the workspace, so only the child that received the first task can recall it. If a follow-up creates a child that inherits the parent thread, that child can replay TOKEN_A from the transcript: the host then fails `history_isolated` and the probe is inconclusive.

## What the six states mean

| Field | True means | False means |
|---|---|---|
| `history_isolated` | The probe ran with parent history inheritance disabled for the initial spawn and for any child created by the follow-up | History was inherited, or the setting could not be confirmed; treat the probe as inconclusive |
| `same_child_confirmed` | The follow-up landed on the child that wrote FILE_A, proven by `TOKEN_A` appearing in FILE_B | A new child, a broadcast, or a dropped message; `TOKEN_A` in FILE_B means some child recalled it, which fails if that child inherited the parent thread |
| `workspace_visible` | The child resolved the given relative path and wrote inside the workspace | The child ran elsewhere, could not resolve the path, or wrote outside the workspace |
| `initial_task_delivered` | The child's reply or behavior references the task or the token, for example it echoes TOKEN_A or reports an error that names the task | The reply is a greeting, a question, a workspace summary, or silence |
| `write_succeeded` | FILE_A exists and its content matches the expected value after newline normalization | No file, wrong content, wrong path, or a write error |
| `followup_delivered` | The second message reached the same child and it acted on it: FILE_B holds the joined value and FILE_A is gone | The follow-up channel is missing, drops the body, or reaches a different child |

`initial_task_delivered` and `write_succeeded` are separate because they are attributed separately: delivery from the reply, write from the file. A greeting with no file sets both to false. A permission error with no file sets delivery true and write false.

## Joint evidence, not three proofs

A single file check is joint evidence for one round of delivery, execution, and write. It shows that this round held together; it does not establish each part independently, and it cannot be reused as proof for a later round. The follow-up repeats the check so `same_child_confirmed` has its own artifact.

## Steps

1. Pick two tokens that match `^[A-Z0-9]{8,64}$` and differ. Pick two workspace-relative paths that do not exist yet, for example `.sot-tmp/probe-delegation-alpha.txt` and `.sot-tmp/probe-delegation-beta.txt`. `.sot-tmp/` is already covered by `.gitignore`; create it if missing.
2. Compute the lowercase hex sha256 of TOKEN_A locally and keep it.
3. Spawn one disposable agent with history inheritance disabled, using the spawn prompt below.
4. Verify FILE_A: it must exist, contain the digest, and match after removing at most one trailing newline. Any other difference is a failure. Record its SHA256 before the follow-up deletes it.
5. Send the follow-up prompt to the same child. It carries TOKEN_B and FILE_B only; the value of TOKEN_A must not appear in it.
6. Verify FILE_B: its content must be `TOKEN_A:TOKEN_B` after the same newline normalization, and FILE_A must no longer exist.
7. Record the SHA256 of FILE_B, delete FILE_B, and remove the probe directory if you created it and it is now empty. FILE_A is already gone.
8. Record the six states, both tokens, both paths, the timestamp, and the log locator.

## Spawn prompt template

```text
Compute the lowercase hexadecimal SHA-256 of the token TOKEN_A.
Write only that digest to FILE_A, relative to the workspace root.
Do not add a trailing newline. Create any missing parent directories.
Do not write TOKEN_A itself to any file. Do not ask questions. Do not summarize the workspace.
Then reply with TOKEN_A and nothing else.
```

## Follow-up prompt template

```text
Write <the token from your first task>:TOKEN_B to FILE_B.
Do not add a trailing newline. Create any missing parent directories.
Then delete FILE_A. Do not ask questions. Reply with done and nothing else.
```

The coordinator fills in TOKEN_B and FILE_B only. Do not repeat the value of TOKEN_A in the follow-up: the child has to recall it from its first task, and that recall is what proves the message reached the same child. A follow-up that contains TOKEN_A proves nothing about same-child delivery.

Keep "do not ask questions" in both messages: a greeting or a clarification request then becomes an unambiguous delivery failure instead of a plausible answer.

## If the child cannot hash

Treat the probe as inconclusive and set `delegation_available: false`. A weaker binding, such as a token suffix written to FILE_A, can be replayed by any child that reads the workspace, so it is not accepted as evidence of same-child delivery.

## Log format

Append one block per call. Include the timestamp, the tool name, the arguments that identify the task, the raw return value, and the file hash you measured yourself.

```text
2026-10-18T12:00:00Z tool=spawn args=agent=probe-a,history=none
2026-10-18T12:00:00Z args=token=PROBEA7F3C1A9D2B,file_a=.sot-tmp/probe-delegation-alpha.txt
2026-10-18T12:00:00Z return=task_name=probe-a,nickname=<host nickname>
2026-10-18T12:00:04Z file_a exists=true content_matches_digest=true sha256=<64 hex>
2026-10-18T12:00:05Z tool=followup args=agent=probe-a,token_b=PROBEB2E48B6C1F7
2026-10-18T12:00:09Z file_b content=PROBEA7F3C1A9D2B:PROBEB2E48B6C1F7 file_a exists=false
```

Quote the file content you read, not the content you sent. A child summary is not a log line. Make the locator cover exactly the lines you cite.

## Decision rule

- All six true: set `delegation_available: true`.
- Any false: set `delegation_available: false`, record the first failing stage, and use the single-agent path with a separate verification pass.
- History inheritance that cannot be disabled makes the other states unusable: report the probe as inconclusive instead of partially passing.
- Never set a state to `true` without a file you read or a log line you captured.
- Never mark the probe available because the spawn call returned an identifier. V2 returns `task_name` and `nickname`; V1 returns `agent_id`. None of them proves delivery.

## When the probe fails

Record the failure instead of retrying until something passes:

- `delegation_available: false` in `host_capabilities`.
- `detection.result: "unavailable"` and `detection.observed` naming the failing stage, for example "spawn accepted, child replied with a greeting, no file was written".
- The probe entry keeps the values you measured, including the booleans that failed, so the next run can compare.
- `fallback.result: "exercised"` only after the single-agent verification pass actually ran.
- Team fields set for one agent. The validator rejects a team when delegation is unavailable.

If the reply never mentions the task, report a host delivery defect with the failing stage - not a model refusal, a prompt problem, or a skill problem. If the child names the task and then refuses to write, say so plainly: delivery worked and the write or policy gate failed.

## Limits

- A passing probe is an entrance ticket, not a guarantee. It does not prove that later messages arrive, that a long prompt survives truncation, or that a different child on the same host behaves the same way.
- The probe does not test reviewer independence, write-scope enforcement, or concurrency limits.
- A passing probe expires with the host build, model, provider, or adapter. Retest after any change, and retest immediately if a child answers with a generic greeting during real work.
