#!/usr/bin/env python3
"""Positive and negative structural tests for validate_task_contract.py."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from typing import Iterator

from validate_task_contract import validate_manifest, validate_text


@contextlib.contextmanager
def temporary_directory() -> Iterator[str]:
    """Create a temporary directory under the current directory.

    Operating-system temp directories are created 0700 and can be inaccessible
    under restricted sandboxes; a current-directory tree uses the same
    permissions the tests already rely on for the workspace.
    """

    base = Path.cwd() / ".sot-tmp"
    base.mkdir(exist_ok=True)
    target = base / uuid.uuid4().hex
    target.mkdir()
    try:
        yield str(target)
    finally:
        shutil.rmtree(target, ignore_errors=True)


def high_risk_contract() -> dict:
    return {
        "contract_version": 1,
        "task_id": "TASK-2026-001",
        "task_goal": "Add retry-safe idempotent submission to a local queue.",
        "non_goals": ["Do not deploy to production.", "Do not call a real webhook."],
        "base_rev": "worktree-snapshot:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "risk": {
            "level": "high",
            "flags": [
                "concurrency",
                "external_side_effect",
                "network",
                "delete",
                "state_migration",
            ],
            "rationale": "Duplicate delivery, cleanup, and network delivery have external consequences.",
        },
        "host_capabilities": {
            "delegation_available": True,
            "single_agent_fallback": True,
            "adapter": "host-delegation-v1",
            "detection": {
                "method": "runtime capability probe via host tool discovery",
                "observed": "delegation primitives are present in the current host",
                "evidence": "probe-host-capabilities.log#L1",
                "timestamp": "2026-10-18T12:00:00Z",
                "result": "available",
            },
            "fallback": {
                "method": "single-agent verification path",
                "observed": "main agent can perform a fresh review and test pass",
                "evidence": "fallback-verification.log#L1",
                "timestamp": "2026-10-18T12:00:00Z",
                "result": "available",
            },
        },
        "team": {
            "mode": "full_gate",
            "max_agents": 3,
            "max_parallel": 2,
            "coordinator": "main",
            "only_coordinator_can_spawn_or_close": True,
            "subagents_may_spawn": False,
            "reviewer_read_only": True,
            "author_reviewer_separated": True,
            "roles": ["writer", "reviewer", "executor"],
            "assignments": {
                "writer": "agent-writer",
                "reviewer": "agent-reviewer",
                "executor": "agent-executor",
            },
        },
        "write_scope": ["src/queue.py", "tests/test_queue.py"],
        "gates": {
            "plan_review": True,
            "code_review": True,
            "independent_execution": True,
        },
        "acceptance": [
            {
                "id": "AC-1",
                "criterion": "Repeated submission does not duplicate delivery.",
                "method": "command",
                "command": "python -m unittest tests.test_queue",
                "evidence": "Command, exit code, timestamp, raw output, and artifact hash.",
            },
            {
                "id": "AC-2",
                "criterion": "Cleanup removes only expired fixture files.",
                "method": "artifact",
                "command": "",
                "evidence": "Before-and-after fixture inventory bound to the revision.",
            },
        ],
        "authorization": {
            "approval_required": True,
            "requested_actions": [
                "call-mock-webhook",
                "delete-expired-test-files",
                "apply-state-migration",
            ],
            "approved_actions": [],
            "stop_before_action": True,
            "note": "Execution is blocked until each concrete action and target is approved.",
        },
        "budget": {
            "max_rounds": 2,
            "agent_timeout_minutes": 30,
            "total_time_minutes": 90,
            "no_progress_rounds": 2,
            "escalation": ["split", "replan", "reduce_scope", "ask_user"],
        },
        "evidence_requirements": {
            "bind_task_id": True,
            "bind_base_rev": True,
            "require_artifact_sha256_or_locator": True,
            "require_command_and_exit_code": True,
            "require_timestamp": True,
            "require_raw_output": True,
            "invalidate_on_artifact_change": True,
        },
    }


def render(contract: dict) -> str:
    return "# Contract\n\n```json\n" + json.dumps(contract, indent=2) + "\n```\n"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_fixture(root: Path, contract: dict, executed_revision: str | None = None) -> dict:
    handoff_text = (
        "# Handoff: "
        + contract["task_id"]
        + "\n\n## Identity\n\n| Field | Value |\n|---|---|\n"
        + "| `task_id` | `"
        + contract["task_id"]
        + "` |\n| `reviewed_revision` | `"
        + contract["base_rev"]
        + "` |\n| `state` | `approved` |\n"
    )
    acceptance_text = (
        "# Acceptance: "
        + contract["task_id"]
        + "\n\n## Identity\n\n| Field | Value |\n|---|---|\n"
        + "| `task_id` | `"
        + contract["task_id"]
        + "` |\n| `executed_revision` | `"
        + contract["base_rev"]
        + "` |\n| `decision` | `pass` |\n"
    )
    probe_text = "probe: delegation available\n"
    fallback_text = "fallback: main agent verified\n"
    artifact_text = "fixture artifact\n"
    (root / "handoff.md").write_text(handoff_text, encoding="utf-8")
    (root / "acceptance.md").write_text(acceptance_text, encoding="utf-8")
    (root / "probe-host-capabilities.log").write_text(probe_text, encoding="utf-8")
    (root / "fallback-verification.log").write_text(fallback_text, encoding="utf-8")
    (root / "artifact.txt").write_text(artifact_text, encoding="utf-8")
    handoff_hash = sha256_file(root / "handoff.md")
    acceptance_hash = sha256_file(root / "acceptance.md")
    probe_hash = sha256_file(root / "probe-host-capabilities.log")
    fallback_hash = sha256_file(root / "fallback-verification.log")
    artifact_hash = sha256_file(root / "artifact.txt")
    return {
        "manifest_version": 1,
        "task_id": contract["task_id"],
        "base_rev": contract["base_rev"],
        "reviewed_revision": contract["base_rev"],
        "executed_revision": executed_revision or contract["base_rev"],
        "handoff": {"path": "handoff.md", "sha256": handoff_hash},
        "acceptance": {
            "path": "acceptance.md",
            "sha256": acceptance_hash,
        },
        "host_evidence": [
            {
                "kind": "detection",
                "path": "probe-host-capabilities.log",
                "sha256": probe_hash,
            },
            {
                "kind": "fallback",
                "path": "fallback-verification.log",
                "sha256": fallback_hash,
            },
        ],
        "artifacts": [{"path": "artifact.txt", "sha256": artifact_hash}],
        "evidence": [
            {
                "task_id": contract["task_id"],
                "base_rev": contract["base_rev"],
                "author": "agent-executor",
                "artifact": "artifact.txt",
                "command": "python -m unittest tests.test_queue",
                "exit_code": 0,
                "timestamp": "2026-10-18T12:00:00Z",
                "scope": "queue retry tests",
                "artifact_sha256": artifact_hash,
                "artifact_locator": "",
                "raw_output": "OK",
            }
        ],
    }


def medium_risk_contract() -> dict:
    contract = high_risk_contract()
    contract["task_id"] = "TASK-2026-002"
    contract["risk"] = {
        "level": "medium",
        "flags": [],
        "rationale": "Two related modules share a reversible internal interface.",
    }
    contract["team"] = {
        "mode": "writer_reviewer",
        "max_agents": 2,
        "max_parallel": 2,
        "coordinator": "main",
        "only_coordinator_can_spawn_or_close": True,
        "subagents_may_spawn": False,
        "reviewer_read_only": True,
        "author_reviewer_separated": True,
        "roles": ["writer", "reviewer"],
        "assignments": {
            "writer": "agent-writer",
            "reviewer": "agent-reviewer",
        },
    }
    contract["gates"] = {
        "plan_review": False,
        "code_review": True,
        "independent_execution": False,
    }
    contract["authorization"] = {
        "approval_required": False,
        "requested_actions": [],
        "approved_actions": [],
        "stop_before_action": True,
        "note": "No external action is requested.",
    }
    return contract


def low_risk_contract() -> dict:
    contract = high_risk_contract()
    contract["task_id"] = "TASK-2026-003"
    contract["risk"] = {
        "level": "low",
        "flags": [],
        "rationale": "One reversible file change with an existing test.",
    }
    contract["team"] = {
        "mode": "single_agent",
        "max_agents": 0,
        "max_parallel": 0,
        "coordinator": "main",
        "only_coordinator_can_spawn_or_close": True,
        "subagents_may_spawn": False,
        "reviewer_read_only": True,
        "author_reviewer_separated": True,
        "roles": [],
        "assignments": {},
    }
    contract["gates"] = {
        "plan_review": False,
        "code_review": False,
        "independent_execution": False,
    }
    contract["authorization"] = {
        "approval_required": False,
        "requested_actions": [],
        "approved_actions": [],
        "stop_before_action": True,
        "note": "No external action is requested.",
    }
    contract["budget"]["max_rounds"] = 1
    return contract


class ValidatorTests(unittest.TestCase):
    def assert_valid(self, contract: dict) -> None:
        self.assertEqual(validate_text(render(contract)), [])

    def assert_invalid(self, contract: dict, expected: str) -> None:
        errors = validate_text(render(contract))
        self.assertTrue(errors, "expected validation errors")
        self.assertTrue(
            any(expected in error for error in errors),
            f"expected {expected!r} in errors: {errors}",
        )

    def test_high_risk_full_gate_passes(self) -> None:
        self.assert_valid(high_risk_contract())

    def test_medium_risk_writer_reviewer_passes(self) -> None:
        self.assert_valid(medium_risk_contract())

    def test_low_risk_no_team_passes(self) -> None:
        self.assert_valid(low_risk_contract())

    def test_missing_task_id_fails(self) -> None:
        contract = high_risk_contract()
        del contract["task_id"]
        self.assert_invalid(contract, "task_id")

    def test_missing_base_rev_fails(self) -> None:
        contract = high_risk_contract()
        del contract["base_rev"]
        self.assert_invalid(contract, "base_rev")

    def test_missing_acceptance_fails(self) -> None:
        contract = high_risk_contract()
        del contract["acceptance"]
        self.assert_invalid(contract, "acceptance")

    def test_missing_risk_fails(self) -> None:
        contract = high_risk_contract()
        del contract["risk"]
        self.assert_invalid(contract, "risk")

    def test_missing_authorization_fails(self) -> None:
        contract = high_risk_contract()
        del contract["authorization"]
        self.assert_invalid(contract, "authorization")

    def test_author_equals_reviewer_fails(self) -> None:
        contract = high_risk_contract()
        contract["team"]["assignments"]["reviewer"] = "agent-writer"
        self.assert_invalid(contract, "author and reviewer must be different")

    def test_path_traversal_fails(self) -> None:
        contract = high_risk_contract()
        contract["write_scope"] = ["../escape.txt"]
        self.assert_invalid(contract, "write_scope")

    def test_low_risk_cannot_delegate(self) -> None:
        contract = low_risk_contract()
        contract["team"] = copy.deepcopy(high_risk_contract()["team"])
        self.assert_invalid(contract, "low risk must use the single-agent path")

    def test_high_risk_requires_plan_review(self) -> None:
        contract = high_risk_contract()
        contract["gates"]["plan_review"] = False
        self.assert_invalid(contract, "high risk requires plan_review=true")

    def test_delegation_unavailable_cannot_form_team(self) -> None:
        contract = high_risk_contract()
        contract["host_capabilities"]["delegation_available"] = False
        self.assert_invalid(contract, "delegation unavailable requires team.mode=single_agent")

    def test_mutable_revision_fails(self) -> None:
        contract = high_risk_contract()
        contract["base_rev"] = "HEAD"
        self.assert_invalid(contract, "base_rev must be an immutable")

    def test_approval_not_requested_fails(self) -> None:
        contract = high_risk_contract()
        contract["authorization"]["approved_actions"] = ["unlisted-action"]
        self.assert_invalid(contract, "approved_actions contains actions not present")

    def test_risky_task_requires_requested_actions(self) -> None:
        contract = high_risk_contract()
        contract["authorization"]["requested_actions"] = []
        contract["authorization"]["approved_actions"] = []
        self.assert_invalid(contract, "requires authorization.requested_actions")

    def test_missing_evidence_requirements_fails(self) -> None:
        contract = high_risk_contract()
        del contract["evidence_requirements"]
        self.assert_invalid(contract, "evidence_requirements")

    def test_placeholder_assignment_fails(self) -> None:
        contract = high_risk_contract()
        contract["team"]["assignments"]["reviewer"] = "TBD"
        self.assert_invalid(contract, "must be a concrete execution unit")

    def test_executor_equals_writer_fails(self) -> None:
        contract = high_risk_contract()
        contract["team"]["assignments"]["executor"] = "agent-writer"
        self.assert_invalid(contract, "executor must be a different execution unit from writer")

    def test_executor_equals_reviewer_fails(self) -> None:
        contract = high_risk_contract()
        contract["team"]["assignments"]["executor"] = "agent-reviewer"
        self.assert_invalid(contract, "executor must be a different execution unit from reviewer")

    def test_state_migration_requires_authorization(self) -> None:
        contract = high_risk_contract()
        contract["authorization"]["requested_actions"] = []
        contract["authorization"]["approved_actions"] = []
        self.assert_invalid(contract, "requires authorization.requested_actions")

    def test_host_detection_placeholder_fails(self) -> None:
        contract = high_risk_contract()
        contract["host_capabilities"]["detection"]["evidence"] = "runtime-detected"
        self.assert_invalid(contract, "detection.evidence must not be a placeholder")

    def test_manifest_matching_hashes_passes(self) -> None:
        contract = high_risk_contract()
        with temporary_directory() as tmp:
            root = Path(tmp)
            manifest = manifest_fixture(root, contract)
            self.assertEqual(validate_manifest(contract, manifest, root), [])

    def test_manifest_old_revision_fails(self) -> None:
        contract = high_risk_contract()
        with temporary_directory() as tmp:
            root = Path(tmp)
            manifest = manifest_fixture(
                root,
                contract,
                executed_revision="worktree-snapshot:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )
            errors = validate_manifest(contract, manifest, root)
            self.assertTrue(
                any("reviewed_revision and executed_revision must match" in error for error in errors),
                errors,
            )

    def test_manifest_hash_mismatch_fails(self) -> None:
        contract = high_risk_contract()
        with temporary_directory() as tmp:
            root = Path(tmp)
            manifest = manifest_fixture(root, contract)
            (root / "handoff.md").write_text("changed after evidence was recorded\n", encoding="utf-8")
            errors = validate_manifest(contract, manifest, root)
            self.assertTrue(
                any("sha256 does not match the linked file" in error for error in errors),
                errors,
            )

    def test_manifest_handoff_revision_marker_fails(self) -> None:
        contract = high_risk_contract()
        with temporary_directory() as tmp:
            root = Path(tmp)
            manifest = manifest_fixture(root, contract)
            handoff_text = (
                "# Handoff\n\n| Field | Value |\n|---|---|\n"
                "| `task_id` | `"
                + contract["task_id"]
                + "` |\n| `reviewed_revision` | `worktree-snapshot:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb` |\n"
                "| `state` | `approved` |\n| `note` | `contains "
                + contract["base_rev"]
                + "` |\n"
            )
            (root / "handoff.md").write_text(handoff_text, encoding="utf-8")
            manifest["handoff"]["sha256"] = sha256_file(root / "handoff.md")
            errors = validate_manifest(contract, manifest, root)
            self.assertTrue(
                any("handoff.reviewed_revision must equal" in error for error in errors),
                errors,
            )

    def test_manifest_missing_handoff_fails(self) -> None:
        contract = high_risk_contract()
        with temporary_directory() as tmp:
            root = Path(tmp)
            manifest = manifest_fixture(root, contract)
            (root / "handoff.md").unlink()
            errors = validate_manifest(contract, manifest, root)
            self.assertTrue(
                any("does not exist: handoff.md" in error for error in errors),
                errors,
            )

    def test_manifest_acceptance_decision_fail_fails(self) -> None:
        contract = high_risk_contract()
        with temporary_directory() as tmp:
            root = Path(tmp)
            manifest = manifest_fixture(root, contract)
            acceptance_text = (
                "# Acceptance\n\n| Field | Value |\n|---|---|\n"
                "| `task_id` | `"
                + contract["task_id"]
                + "` |\n| `executed_revision` | `"
                + contract["base_rev"]
                + "` |\n\n- Decision: fail\n"
            )
            (root / "acceptance.md").write_text(acceptance_text, encoding="utf-8")
            manifest["acceptance"]["sha256"] = sha256_file(root / "acceptance.md")
            errors = validate_manifest(contract, manifest, root)
            self.assertTrue(
                any("acceptance.decision must be pass" in error for error in errors),
                errors,
            )

    def test_manifest_host_evidence_missing_fails(self) -> None:
        contract = high_risk_contract()
        with temporary_directory() as tmp:
            root = Path(tmp)
            manifest = manifest_fixture(root, contract)
            del manifest["host_evidence"]
            errors = validate_manifest(contract, manifest, root)
            self.assertTrue(
                any("host_evidence must be a non-empty list" in error for error in errors),
                errors,
            )

    def test_manifest_host_evidence_missing_file_fails(self) -> None:
        contract = high_risk_contract()
        with temporary_directory() as tmp:
            root = Path(tmp)
            manifest = manifest_fixture(root, contract)
            manifest["host_evidence"][0]["path"] = "does-not-exist.log"
            errors = validate_manifest(contract, manifest, root)
            self.assertTrue(
                any("does not exist: does-not-exist.log" in error for error in errors),
                errors,
            )

    def test_worker_cannot_equal_coordinator(self) -> None:
        contract = high_risk_contract()
        contract["team"]["assignments"]["writer"] = "main"
        self.assert_invalid(contract, "team.assignments.writer must not equal the coordinator")

    def test_identity_comparison_is_case_insensitive(self) -> None:
        contract = high_risk_contract()
        contract["team"]["assignments"]["reviewer"] = "Agent-Writer"
        self.assert_invalid(contract, "author and reviewer must be different execution units")

    def test_cli_manifest_matching_hashes_passes(self) -> None:
        contract = high_risk_contract()
        with temporary_directory() as tmp:
            root = Path(tmp)
            contract_path = root / "contract.md"
            manifest_path = root / "manifest.md"
            contract_path.write_text(render(contract), encoding="utf-8")
            manifest = manifest_fixture(root, contract)
            manifest_path.write_text(
                "# Manifest\n\n```json\n" + json.dumps(manifest, indent=2) + "\n```\n",
                encoding="utf-8",
            )
            script = Path(__file__).with_name("validate_task_contract.py")
            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    str(contract_path),
                    "--manifest",
                    str(manifest_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
