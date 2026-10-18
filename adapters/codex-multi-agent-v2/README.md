# Codex Multi-Agent Adapter

This adapter covers hosted delegation in Codex Desktop and the Codex CLI. It documents a host defect and how to detect it. It does not change how this skill routes risk.

Codex ships two delegation implementations. `multi_agent_v1` and `multi_agent_v2` differ in tool signatures and in how a task body reaches the child agent. The same skill, the same workspace, and the same permissions can therefore behave differently on two machines.

## Which version is running

Read the tool signatures the session exposes:

| Implementation | Tools |
|---|---|
| V2 | `spawn_agent(task_name, fork_turns, message)`, `followup_task`, `send_message` |
| V1 | `spawn_agent(fork_context)`, `send_input` |

The `fork_turns` parameter with values such as `none` or `all` is V2 only. If the session shows `fork_context`, it is V1 and this adapter's defect section does not apply.

Tool presence alone does not prove that a task is delivered. Run the skill's round-trip probe from `templates/delegation-probe.md` on either version.

## Known defect: plaintext tasks encoded as ciphertext

On a non-OpenAI provider, V2 classifies an ordinary plaintext task as an encrypted message. The child agent starts, receives the message envelope, can read the shared workspace, and cannot see the task body.

The message is not dropped. It is delivered with an empty `content` field, and the task text is placed in `encrypted_content`. The child still receives a readable envelope header: `Message Type`, `Task name`, `Sender`, and `Payload:`. It can see that a message exists and who sent it, but the task body exists only inside `EncryptedContent`, which a non-OpenAI model cannot decrypt.

Source references, checked against `openai/codex` main as of 2026-10-18. All paths are relative to the repository root of `openai/codex`:

| Location | Behavior |
|---|---|
| `codex-rs/core/src/tools/router.rs:56-71` | Marks a call as `DirectPlaintextMessage` only when `encrypted_function_args` is `Some(empty)`; every other case becomes `Direct` |
| `codex-rs/core/src/tools/handlers/multi_agents_v2.rs:54-66` | Any non-plaintext call becomes `AgentMessage::Encrypted`, including an ordinary task string |
| `codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs:221-226` | Defaults `fork_turns` to `all`, so the child inherits the parent thread, including the parent's spawn arguments |
| `codex-rs/core/src/agent/control/delivery.rs:20-26` | `Encrypted` messages are built with `new_encrypted`, so `content` is empty and the body lands in `encrypted_content` |
| `codex-rs/protocol/src/protocol.rs:992-1015` | The child model input has a readable `InputText` envelope header, then `AgentMessageInputContent::EncryptedContent` for the body |
| `codex-rs/core/src/client.rs:1013-1030` | A non-OpenAI provider clears `encrypted_function_args` to `None`, so the router's `Some(empty)` test never matches and plaintext is misclassified |

The last row is the trigger. The rows above it are why the consequence is silent.

## Symptoms

- The child reads the workspace and can list files, so the workspace and sandbox look healthy.
- The child replies with a greeting, asks what you want it to do, or summarizes the repository.
- V2 `spawn_agent` returns `task_name` and `nickname`; only V1 returns `agent_id`. None of them proves that the task was delivered.
- `wait_agent` reports completion, and the final message is a greeting rather than a task result.
- `followup_task` and `send_message` appear to succeed and produce the same behavior, because they share the encoding path.
- No error, no permission failure, and no tool error appears in any of it.

Do not read these symptoms as a model refusal, a prompt problem, or an authorization downgrade. The task never reached the model.

## Workaround

1. Disable the V2 feature in `~/.codex/config.toml`:

   ```text
   [features]
   multi_agent_v2 = false
   ```

2. Check the model catalog entry for the selected model. If it contains `"multi_agent_version": "v2"`, change it to `"v1"` or remove the key. A model catalog setting overrides the collaboration default and can keep V2 active after the feature flag is cleared.
3. Precedence is: feature flag, then model catalog entry, then the collaboration default of V1. Check all three when the first change has no effect.
4. Restart Codex, then rerun the probe from `templates/delegation-probe.md`. A restart without a probe is not a fix; the failure mode produces no error.

`fork_turns: "all"` is a temporary detour for real work, and it is never acceptable for the probe. A probe must run with `fork_turns: "none"`: with `all`, the V2 default, the child inherits the parent thread, including the spawn arguments that contain the probe token, so it can write the expected file without any delivery. Inheritance also does not repair the encoding path or make later messages readable.

A probe run with inherited history is not evidence. It answers "did some child write a file", not "did this child receive this task".

If a managed configuration pins V2 and cannot be edited, use a Codex build that defaults to V1, or stay on V1 until the upstream defect is fixed.

## What the skill does about it

A failed probe sets `delegation_available: false`. The skill then runs the single-agent path with a separate verification pass, and the contract records the failing stage and the measured values. This is the normal fallback, not a special case for Codex.

Do not mark delegation available because the tools exist, because a spawn returned a task name or agent id, or because a child produced a plausible-looking reply. Only a file written by the child, bound to a token the child had to receive, and read back by the coordinator counts. The probe must run with history inheritance disabled.

## Limits

- Based on the `openai/codex` main source, the V1 tool surface observed locally, and the V2 tool surface reported from another machine. Not reproduced end to end on that machine.
- The source locations and the default version may change in later builds. Recheck the tool signatures before trusting this document.
- This adapter is unofficial. It is not a Codex endorsement, and it does not describe any private or undocumented provider behavior beyond the delivery path above.
