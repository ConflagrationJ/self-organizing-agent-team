# DeepSeek Harness Adapter

This directory maps the skill onto DeepSeek Harness (DSH) Agent Teams. It is documentation only: it contains no plugin code and changes no profile state. It is unofficial and experimental; DSH tool schemas, limits, and profile composition can change between releases.

Checked against DSH Desktop 44.7.0, profile `desktop`, on 2026-10-18.

## 1. Prerequisites: the Team composition must be mounted

Agent Teams is an experimental package family, not a default capability. The protocol needs these nine tools, and all of them are scoped to Team members:

`spawn_teammate` · `send_message` · `list_agents` · `wait_agent` · `interrupt_agent` · `team_task_create` · `team_task_list` · `team_task_get` · `team_task_update`

Check before promising a team:

1. Call `list_agents`. A mounted Team service returns the Lead row (`role: lead`); without it the call fails.
2. Confirm the nine tool names above are callable.
3. If either check fails, do not simulate a team. Use the Lead-only path, record the probe output as `host_capabilities.detection`, and state that no team was created.

The shipped Desktop app already composes `@deepseek-ai/dsh-experimental-agent-team-profile`, which mounts durable session storage (`@deepseek-ai/dsh-session-persistence-jsonl`) plus `@deepseek-ai/dsh-experimental-agent-team`, `@deepseek-ai/dsh-experimental-tool-agent-team`, and the team UI projection. In that profile the `agent-team` row is configured with:

| Limit | Shipped Desktop value | Package default |
|---|---|---|
| `maxMembers` | `8` | `16` |
| `maxTasks` | `256` | `256` |
| `maxMessageBytes` | `65536` | `65536` |
| `disposalTimeoutMs` | `5000` | `5000` |

`maxMembers` counts every teammate ever created, including failed creations. The adapter's own policy cap of three teammates is stricter and is what this protocol enforces.

To change a limit, override the `agent-team` row in the profile `cordis.patch.yml`. To add Agent Teams to another composition, mount the three packages listed in the `agent-team` package README (durable storage is required). The exact command-line form of profile installation differs between DSH distributions, and the shipped Desktop build exposes no `dsh` executable on `PATH`; prefer the profile bundle definition or the plugin manager over a hard-coded command. Do not copy plugin source into the workspace.

Refresh an already-open page only if the roster UI does not appear after enablement. What actually matters is that the nine tools are callable by the Lead.

## 2. Two delegation mechanisms can be visible

DSH can expose both the Team tools above and the older `subagent` / `subagent_fork` tools in the same composition (the shipped Desktop profile does on the checked build). They are not interchangeable:

| Mechanism | Creates | Roster / ownership | Task board | Fits this protocol |
|---|---|---|---|---|
| Team tools | named durable teammates | yes | yes | yes |
| `subagent` / `subagent_fork` | anonymous child agents | no roster, no owner | no | no |

Rules:

- Use the Team tools for every delegated role in this protocol.
- A `subagent` child is not a team member: it has no `target`, cannot own a task, and its result does not satisfy any review gate.
- Tell every teammate not to call `subagent` or `subagent_fork`. A teammate that spawns a nested child breaks the roster, the two-round cap, and the "no nested delegation" invariant. Treat any nested delegation as a stop condition.
- Do not mix mechanisms inside one task; a task contract lists one delegation mechanism in `host_capabilities.adapter` (`dsh-agent-team-v1`).

## 3. Install this skill for DSH

DSH discovers a skill as either a directory bundle `<name>/SKILL.md` or a flat file `<name>.md` directly under one scanned root. There is no centralized registry install step.

| Rank | Root | Notes |
|---|---|---|
| 100 | `<project>/.dsh/skills` | project root is the nearest ancestor containing `.git`, otherwise the current working directory |
| 200 | `<project>/.agents/skills` | |
| 300 | configured `customSkillDirs` | |
| 400 | `<dshHome>/skills` | `dshHome` is `C:\Users\<user>\.dsh` on this machine |
| 500 | `~/.agents/skills` | shared agent configuration root |
| 600 | bundled skill dir | shipped by DSH |

Copy the whole `self-organizing-agent-team/` directory (not only `SKILL.md`) into one of those roots, keeping the directory name. `SKILL.md` resources such as `references/`, `templates/`, and `scripts/` resolve against the bundle's base directory.

Important: `~/.codex/skills/` is **not** one of the DSH roots. A Codex install at `C:\Users\<user>\.codex\skills\self-organizing-agent-team` will not appear in DSH. Either copy the bundle into a DSH root or create a directory junction, for example:

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.dsh\skills\self-organizing-agent-team" `
  -Target "$env:USERPROFILE\.codex\skills\self-organizing-agent-team"
```

Verification: the next session catalog lists `self-organizing-agent-team`; a direct check is the `skill` tool with that exact name. Root watching makes new bundles visible without a restart.

### Explicit invocation only

DSH has no `allow_implicit_invocation` switch and ignores `agents/openai.yaml` (that file is a Codex convention). A discovered skill is model-invocable by default: the model sees its name and capped description and decides when to load it.

If you want the Codex release policy "explicit invocation only" on DSH, add this line to the frontmatter of the installed copy:

```yaml
disable-model-invocation: true
```

The skill then disappears from the model catalog, while a user-invocable `/self-organizing-agent-team` token in direct user input still injects the instructions. Choose one policy per install and record it; do not rely on a host to infer the other host's policy.

## 4. Make the protocol reachable

All team members share one working directory, so a single protocol file is enough. Options, in order of preference:

1. Tell the Lead to read `TEAM-PROTOCOL.md` from this bundle and include its path in every teammate spawn prompt.
2. Copy `TEAM-PROTOCOL.md` to a workspace path (for example `team-protocol.md`) and name that single copy as authoritative.
3. Restate the essentials inline in each spawn prompt.

A `fresh` teammate inherits none of the Lead's conversation, so it knows only its system policy, its initial prompt, and files it reads. Do not assume a teammate has read the protocol because the Lead did. Teammates run in the shared working directory and can read any file the Lead names; a member may also be able to load the skill if its tool set exposes the `skill` tool, but do not rely on that — include the task package and the protocol path in the spawn prompt.

## 5. Tool mapping and caveats

| Tool | Role in the protocol | DSH behavior to respect |
|---|---|---|
| `spawn_teammate` | create writer / reviewer / executor | Lead only; `name` is lower-kebab-case, permanent, never reused; `context` is `fresh` (default) or `fork`; `prompt` is the teammate's entire initial task |
| `send_message` | send a task package, a wake-up, or a finding | any member to any member; success means inbox acceptance only; no retry, no deduplication; message cap 64 KiB; self-messaging rejected |
| `list_agents` | roster, availability, `target` values | `inactive` means no turn is executing, not success or completion; `provisioning` and `failed` describe creation |
| `wait_agent` | block for the next team change | 10 s to 1 h; reports only change/timeout; returns `noProgress` immediately when no other member is running or provisioning; always re-read state afterwards |
| `interrupt_agent` | stop a runaway turn | Lead only; registered in the shipped Desktop profile; cancels the current turn but keeps the inbox and does not release task ownership |
| `team_task_create` | one unit of work | returns a board-assigned id such as `task-1`; new tasks are unowned and pending |
| `team_task_list` | dashboard | filter by `status`, `owner`, `ready`; shows revision, blockers, write-scope warnings |
| `team_task_get` | read before mutation | returns the current revision |
| `team_task_update` | claim / release / complete / reopen / reassign / edit / set_dependencies / delete | every mutation is compare-and-set on `expected_revision`; stale revisions are rejected; `reassign` is Lead-only; `delete` is a tombstone, never a completion state |

`write_scopes` are advisory: DSH warns when two in-progress tasks plan overlapping paths and never blocks a write. Bash, formatters, code generators, and direct file writes can bypass ownership. The Lead must inspect the final diff.

## 6. Spawning rules that prevent most team failures

- Use `context: fresh` for the writer, reviewer, and executor. `fork` inherits the Lead's completed turns, including anything the Lead already read from the writer, which contaminates reviewer independence. Reserve `fork` for non-gated work that genuinely needs the Lead's context.
- Choose all names before writing the contract: `team.assignments` needs the exact teammate `target` values, and a name reserved by a failed creation cannot be reused or deleted.
- Put the whole task package in the initial `prompt`: task id, board task id, base revision, write scope, inputs, gates, stop conditions, and the path of the protocol copy. `spawn_teammate` delivers that prompt unchanged.
- All members receive the same nine tools. Lead-only operations are enforced when called, not by hiding the tools. Tell teammates explicitly that they must not spawn or interrupt members.
- Failed creations consume `maxMembers` capacity. Plan for one spawn per role and keep the team under three teammates.

## 7. Task board and the contract

DSH assigns task ids (`task-<n>`). The task contract's `task_id` should be that board id so the contract, deck, handoff, and evidence all name the same object; put the human-readable label in the task subject instead. Because the id exists only after creation, the boot order is:

1. classify risk and choose role names;
2. `team_task_create` for each unit of work, including `blocked_by` and `write_scopes`;
3. write the task contract using the returned ids and the chosen names;
4. spawn the teammates and send each one its package.

Then the normal rule applies: `team_task_get` before every mutation, and never overwrite a newer revision.

The board limits what a task claim can do: a task is claimable only when every `blocked_by` entry is complete, and the owner is never released automatically by inactivity, interruption, process exit, or failure. The Lead must reassign, release, or complete explicitly. Deleted tasks remain as tombstones for id stability.

## 8. Revision binding without a mandatory VCS

The evidence envelope needs an immutable `base_rev`. A revision format that assumes Git cannot be executed in a workspace without `.git`. Use either:

- `git rev-parse HEAD` (plus a working-tree hash) when the project is a Git repository, recorded as the exact command and output; or
- the bundled snapshot tool:

```powershell
python scripts/snapshot_worktree.py .            # prints worktree-snapshot:<sha256>
python scripts/snapshot_worktree.py . --json     # machine-readable
```

The snapshot hashes sorted relative paths and file bytes, skipping `.git`, `__pycache__`, `.dsh`, `.venv`, `node_modules`, and temp directories. Two runs over an unchanged tree print the same value; any edit changes it. Freeze the snapshot before the reviewer starts and recompute it after review: a changed value invalidates the review.

Large diffs and logs do not fit in a 64 KiB team message. Write them to workspace files and send the locator plus the snapshot value.

## 9. Limits that remain

- One shared working directory. No worktree isolation, merge step, or file lock.
- `write_scopes` warn; they do not prevent writes.
- No per-member read-only mode. Reviewer read-only is a Lead-enforced rule; compare pre-review and post-review snapshots and invalidate any review-time write.
- `inactive` is not done, failed, or complete. A teammate that finished a turn usually goes `inactive`.
- Task owners are never released automatically.
- `send_message` acceptance is not processing; there is no retry or deduplication.
- `wait_agent` can return `noProgress` immediately; that is not a teammate failure.
- `interrupt_agent` is registered on the checked profile but is optional across compositions.
- Team packages are experimental and carry no stability promise; the Desktop composition may change between releases.
- The Lead must inspect the final diff and run the final tests. A teammate summary is not acceptance evidence.

## 10. Copy-paste prompt for the DSH Lead

```text
1. You are the DSH Lead for this workspace.
2. Read TEAM-PROTOCOL.md from the adapter bundle before creating any teammate.
3. Classify the task as low, medium, or high risk under that protocol.
4. If the Team tools are unavailable, do not simulate a team: work as one agent, record the probe, and say no team was created.
5. If the risk is low, do not call spawn_teammate; work directly, then reread the diff, run the relevant tests, and record evidence.
6. If Agent Teams is mounted, use only the nine Team tools; do not use subagent or subagent_fork.
7. Create the board tasks first, then write the contract with the returned task ids as task_id.
8. Name the teammates in the contract and spawn them with context: fresh.
9. Put the full task package in each spawn prompt, including the protocol path.
10. For medium risk, spawn writer and reviewer. For high risk, spawn writer, reviewer, and executor; cap is three teammates.
11. Never let the Lead act as writer, reviewer, or executor; the Lead validates the final result.
12. Reviewer receives the contract, base snapshot, raw diff or files, and raw logs before any writer conclusion.
13. Compare the snapshot before and after review; any reviewer write invalidates the review.
14. High risk requires plan review before implementation and code review after implementation.
15. Require explicit user approval for each external side effect and irreversible action; DSH sandbox permission is not user intent.
16. Do not treat inactive as done and do not release owners automatically; reassign or complete explicitly.
17. After wait_agent returns, re-read list_agents, team_task_get, and team_task_list; noProgress means wake someone, not failure.
18. Stop on failed creation, a stale revision loop, a changed snapshot after review, or two unresolved writer-reviewer rounds.
19. Check the final diff and rerun the final tests yourself; do not rely on teammate summaries.
20. Report changed files, tests, blockers, and residual risk.
```

## 11. Contract field mapping

| Contract field | DSH value |
|---|---|
| `task_id` | board id, e.g. `task-1` |
| `host_capabilities.adapter` | `dsh-agent-team-v1` |
| `host_capabilities.detection.evidence` | file with `list_agents` / tool-list probe output |
| `team.coordinator` | `lead` |
| `team.assignments.writer/reviewer/executor` | teammate `target` names, e.g. `writer`, `reviewer`, `executor` |
| `team.max_agents` | `3` (high), `2` (medium), `0` (low) |
| `team.max_parallel` | `2` at most; the Lead enforces it by serializing `blocked_by` work |
| `write_scope` | workspace-relative prefixes passed to `team_task_create.write_scopes` |
| `base_rev` | `worktree-snapshot:<sha256>` or the exact Git command and output |

## 12. What this adapter does not do

- It does not implement, install, or configure a DSH plugin or profile.
- It does not make a reviewer read-only, enforce write scopes, or release task owners.
- It does not replace DSH's own Team policy, approval flow, or sandbox; that policy stays authoritative and this skill only adds risk routing and gates.
