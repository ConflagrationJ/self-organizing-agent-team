# Evidence Manifest

Link the task contract to its handoff, acceptance, artifacts, and evidence. Paths are relative to this manifest file and must remain inside the manifest directory. Replace the sample values with real files and hashes before validation.

```json
{
  "manifest_version": 1,
  "task_id": "TASK-2026-001",
  "base_rev": "worktree-snapshot:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "reviewed_revision": "worktree-snapshot:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "executed_revision": "worktree-snapshot:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "handoff": {
    "path": "handoff.md",
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "acceptance": {
    "path": "acceptance.md",
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "host_evidence": [
    {
      "kind": "detection",
      "path": "probe-host-capabilities.log",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    {
      "kind": "fallback",
      "path": "fallback-verification.log",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  ],
  "artifacts": [
    {
      "path": "src/queue.py",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  ],
  "evidence": [
    {
      "task_id": "TASK-2026-001",
      "base_rev": "worktree-snapshot:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "author": "agent-executor",
      "artifact": "src/queue.py",
      "command": "python -m unittest tests.test_queue",
      "exit_code": 0,
      "timestamp": "2026-10-18T12:00:00Z",
      "scope": "queue retry tests",
      "artifact_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "artifact_locator": "",
      "raw_output": "OK"
    }
  ]
}
```

The validator verifies shape and file hashes. It does not prove that the handoff was written by the named agent, that the reviewer was independent, or that the raw output is truthful.
