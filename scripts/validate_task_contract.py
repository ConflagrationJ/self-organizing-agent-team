#!/usr/bin/env python3
"""Validate the structure of a Markdown task contract.

This script checks shape and explicit policy fields only. It cannot prove that
the risk choice is correct, that evidence was produced, or that a reviewer was
independent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


JSON_BLOCK_RE = re.compile(r"```json[ \t]*\r?\n(.*?)\r?\n```", re.DOTALL | re.IGNORECASE)
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
REVISION_RE = re.compile(
    r"^(?:[0-9a-fA-F]{7,64}|(?:git|sha256|worktree-snapshot):[0-9a-fA-F]{7,64})$"
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
FIELD_TABLE_RE = re.compile(
    r"^\s*\|\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\|\s*`?([^|`]+?)`?\s*\|\s*$"
)
FIELD_COLON_RE = re.compile(
    r"^\s*(?:[-*]\s*)?`?([A-Za-z_][A-Za-z0-9_]*)`?\s*[:=]\s*`?([^`\n]+?)`?\s*$"
)

RISK_LEVELS = {"low", "medium", "high"}
TEAM_MODES = {"single_agent", "writer_reviewer", "full_gate"}
ROLES = {"writer", "reviewer", "executor", "analyst", "monitor"}
METHODS = {"command", "artifact", "manual"}
ESCALATIONS = {"split", "replan", "reduce_scope", "ask_user"}
PLACEHOLDER_VALUES = {
    "tbd",
    "tba",
    "todo",
    "unknown",
    "unassigned",
    "none",
    "null",
    "n/a",
    "na",
    "placeholder",
    "runtime-detected",
}
CAPABILITY_RESULTS = {"available", "unavailable", "exercised"}

PROBE_BOOLEAN_KEYS = (
    "history_isolated",
    "same_child_confirmed",
    "workspace_visible",
    "initial_task_delivered",
    "write_succeeded",
    "followup_delivered",
)
PROBE_TOKEN_KEYS = ("token_a", "token_b")
PROBE_FILE_KEYS = ("file_a", "file_b")
PROBE_TEXT_KEYS = PROBE_TOKEN_KEYS + PROBE_FILE_KEYS + ("evidence", "timestamp")
PROBE_TOKEN_RE = re.compile(r"^[A-Z0-9]{8,64}$")

RISK_FLAGS = {
    "concurrency",
    "locks",
    "permissions",
    "secrets_pii",
    "migration",
    "state_migration",
    "network",
    "delete",
    "overwrite",
    "publish",
    "payment",
    "production",
    "external_side_effect",
    "git_history",
    "dependency_install",
    "ci_release",
    "bulk_change",
    "availability",
    "data_loss",
}

AUTHORIZATION_FLAGS = {
    "permissions",
    "secrets_pii",
    "migration",
    "state_migration",
    "network",
    "delete",
    "overwrite",
    "publish",
    "payment",
    "production",
    "external_side_effect",
    "git_history",
    "dependency_install",
    "ci_release",
    "bulk_change",
}


def _is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDER_VALUES


def _assignment_id(value: str) -> bool:
    return bool(value.strip()) and not _is_placeholder(value)


def _parse_markdown_fields(
    text: str,
    label: str,
    errors: list[str],
) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = FIELD_TABLE_RE.match(line) or FIELD_COLON_RE.match(line)
        if not match:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        if not value:
            continue
        if key in fields and fields[key].casefold() != value.casefold():
            errors.append(f"{label}.{key} has conflicting duplicate values")
            continue
        fields[key] = value
    return fields


def _mapping(parent: dict[str, Any], key: str, label: str, errors: list[str]) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def _string(parent: dict[str, Any], key: str, label: str, errors: list[str]) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
        return ""
    return value.strip()


def _boolean(parent: dict[str, Any], key: str, label: str, errors: list[str]) -> bool | None:
    value = parent.get(key)
    if not isinstance(value, bool):
        errors.append(f"{label} must be a boolean")
        return None
    return value


def _integer(
    parent: dict[str, Any],
    key: str,
    label: str,
    errors: list[str],
    minimum: int,
    maximum: int,
) -> int | None:
    value = parent.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{label} must be an integer")
        return None
    if value < minimum or value > maximum:
        errors.append(f"{label} must be between {minimum} and {maximum}")
        return None
    return value


def _string_list(
    parent: dict[str, Any],
    key: str,
    label: str,
    errors: list[str],
    *,
    allow_empty: bool = False,
) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    if not allow_empty and not value:
        errors.append(f"{label} must not be empty")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}[{index}] must be a non-empty string")
        else:
            result.append(item.strip())
    return result


def _bound_revision(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"head", "main", "master", "latest", "none", "tbd"}:
        return False
    return bool(REVISION_RE.fullmatch(value.strip()))


def _safe_relative_path(value: str) -> bool:
    raw = value.strip()
    if not raw or "\x00" in raw:
        return False
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("~"):
        return False
    if re.match(r"^[A-Za-z]:", normalized):
        return False
    if any(token in normalized for token in ("*", "?", "[")):
        return False
    parts = PurePosixPath(normalized).parts
    if not parts or parts == (".",):
        return False
    return not any(part == ".." for part in parts)


def _validate_risk(contract: dict[str, Any], errors: list[str]) -> tuple[str, set[str]]:
    risk = _mapping(contract, "risk", "risk", errors)
    level = _string(risk, "level", "risk.level", errors)
    if level and level not in RISK_LEVELS:
        errors.append("risk.level must be low, medium, or high")
    flags = _string_list(risk, "flags", "risk.flags", errors, allow_empty=True)
    unknown = [flag for flag in flags if flag not in RISK_FLAGS and not flag.startswith("custom:")]
    if unknown:
        errors.append("risk.flags contains unsupported values: " + ", ".join(unknown))
    _string(risk, "rationale", "risk.rationale", errors)
    return level, set(flags)


def _validate_capability_record(
    host: dict[str, Any],
    key: str,
    label: str,
    allowed_results: set[str],
    errors: list[str],
) -> str:
    record = _mapping(host, key, label, errors)
    for field in ("method", "observed", "evidence", "timestamp"):
        value = _string(record, field, f"{label}.{field}", errors)
        if value and _is_placeholder(value):
            errors.append(f"{label}.{field} must not be a placeholder")
    result = _string(record, "result", f"{label}.result", errors)
    if result and result not in allowed_results:
        errors.append(f"{label}.result must be one of: {', '.join(sorted(allowed_results))}")
    return result


def _validate_delegation_probe(
    detection: dict[str, Any],
    label: str,
    available: bool | None,
    errors: list[str],
) -> None:
    probe = detection.get("probe")
    if probe is None:
        if available is True:
            errors.append(f"{label}.probe is required when delegation_available=true")
        return
    if not isinstance(probe, dict):
        errors.append(f"{label}.probe must be an object")
        return

    if available is True:
        for key in PROBE_BOOLEAN_KEYS:
            if probe.get(key) is not True:
                errors.append(
                    f"{label}.probe.{key} must be true when delegation_available=true"
                )
    else:
        for key in PROBE_BOOLEAN_KEYS:
            if key in probe and not isinstance(probe[key], bool):
                errors.append(f"{label}.probe.{key} must be a boolean")

    values: dict[str, str] = {}
    for key in PROBE_TEXT_KEYS:
        if key not in probe:
            if available is True:
                errors.append(f"{label}.probe.{key} must be a non-empty string")
            continue
        raw = probe[key]
        if not isinstance(raw, str) or not raw.strip():
            errors.append(f"{label}.probe.{key} must be a non-empty string")
            continue
        value = raw.strip()
        if _is_placeholder(value):
            errors.append(f"{label}.probe.{key} must not be a placeholder")
        values[key] = value

    if available is not True:
        return

    for key in PROBE_TOKEN_KEYS:
        value = values.get(key, "")
        if value and not PROBE_TOKEN_RE.fullmatch(value):
            errors.append(f"{label}.probe.{key} must match ^[A-Z0-9]{{8,64}}$")
    for key in PROBE_FILE_KEYS:
        value = values.get(key, "")
        if value and not _safe_relative_path(value):
            errors.append(
                f"{label}.probe.{key} must be a project-relative path "
                "without traversal or globs"
            )

    token_a = values.get("token_a", "")
    token_b = values.get("token_b", "")
    if token_a and token_b and token_a == token_b:
        errors.append(f"{label}.probe.token_b must differ from {label}.probe.token_a")
    file_a = values.get("file_a", "")
    file_b = values.get("file_b", "")
    if file_a and file_b and file_a == file_b:
        errors.append(f"{label}.probe.file_b must differ from {label}.probe.file_a")


def _validate_host(contract: dict[str, Any], errors: list[str]) -> bool | None:
    host = _mapping(contract, "host_capabilities", "host_capabilities", errors)
    available = _boolean(
        host,
        "delegation_available",
        "host_capabilities.delegation_available",
        errors,
    )
    fallback = _boolean(
        host,
        "single_agent_fallback",
        "host_capabilities.single_agent_fallback",
        errors,
    )
    adapter = host.get("adapter")
    if adapter is not None:
        if not isinstance(adapter, str) or not adapter.strip():
            errors.append("host_capabilities.adapter must be a non-empty string when present")
        elif _is_placeholder(adapter):
            errors.append("host_capabilities.adapter must not be a placeholder")

    detection_result = _validate_capability_record(
        host,
        "detection",
        "host_capabilities.detection",
        {"available", "unavailable"},
        errors,
    )
    detection = host.get("detection")
    if isinstance(detection, dict):
        _validate_delegation_probe(
            detection,
            "host_capabilities.detection",
            available,
            errors,
        )
    fallback_result = _validate_capability_record(
        host,
        "fallback",
        "host_capabilities.fallback",
        {"available", "exercised"},
        errors,
    )
    if fallback is False:
        errors.append("host_capabilities.single_agent_fallback must be true")
    if available is True and detection_result and detection_result != "available":
        errors.append("delegation_available=true requires detection.result=available")
    if available is False and detection_result and detection_result != "unavailable":
        errors.append("delegation_available=false requires detection.result=unavailable")
    if available is False and fallback_result and fallback_result != "exercised":
        errors.append("delegation unavailable requires fallback.result=exercised")
    return available


def _validate_team(
    contract: dict[str, Any],
    risk_level: str,
    delegation_available: bool | None,
    errors: list[str],
) -> tuple[int | None, dict[str, str]]:
    team = _mapping(contract, "team", "team", errors)
    mode = _string(team, "mode", "team.mode", errors)
    if mode and mode not in TEAM_MODES:
        errors.append("team.mode must be single_agent, writer_reviewer, or full_gate")

    max_agents = _integer(team, "max_agents", "team.max_agents", errors, 0, 3)
    max_parallel = _integer(team, "max_parallel", "team.max_parallel", errors, 0, 2)
    if max_agents is not None and max_parallel is not None and max_parallel > max_agents:
        errors.append("team.max_parallel must not exceed team.max_agents")

    coordinator = _string(team, "coordinator", "team.coordinator", errors)
    if coordinator and _is_placeholder(coordinator):
        errors.append("team.coordinator must not be a placeholder")
    exclusive = _boolean(
        team,
        "only_coordinator_can_spawn_or_close",
        "team.only_coordinator_can_spawn_or_close",
        errors,
    )
    if exclusive is False:
        errors.append("only the coordinator may spawn or close subagents")

    may_spawn = _boolean(team, "subagents_may_spawn", "team.subagents_may_spawn", errors)
    if may_spawn is True:
        errors.append("team.subagents_may_spawn must be false in this release")

    reviewer_read_only = _boolean(
        team, "reviewer_read_only", "team.reviewer_read_only", errors
    )
    if reviewer_read_only is False:
        errors.append("team.reviewer_read_only must be true")

    separated = _boolean(
        team,
        "author_reviewer_separated",
        "team.author_reviewer_separated",
        errors,
    )
    roles = _string_list(team, "roles", "team.roles", errors, allow_empty=True)
    unknown_roles = [role for role in roles if role not in ROLES]
    if unknown_roles:
        errors.append("team.roles contains unsupported values: " + ", ".join(unknown_roles))
    if len(set(roles)) != len(roles):
        errors.append("team.roles must not contain duplicates")
    if max_agents is not None and len(roles) > max_agents:
        errors.append("team.roles exceeds team.max_agents")

    assignments_raw = team.get("assignments", {})
    if assignments_raw is None:
        assignments_raw = {}
    if not isinstance(assignments_raw, dict):
        errors.append("team.assignments must be an object when present")
        assignments: dict[str, str] = {}
    else:
        assignments = {}
        for key, value in assignments_raw.items():
            if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
                errors.append("team.assignments values must be non-empty strings")
            else:
                if key not in ROLES:
                    errors.append(f"team.assignments contains unsupported role: {key}")
                if not _assignment_id(value):
                    errors.append(
                        f"team.assignments.{key} must be a concrete execution unit, not a placeholder"
                    )
                assignments[key] = value.strip()

    writer = assignments.get("writer", "")
    reviewer = assignments.get("reviewer", "")
    executor = assignments.get("executor", "")
    writer_key = writer.casefold()
    reviewer_key = reviewer.casefold()
    executor_key = executor.casefold()
    coordinator_key = coordinator.casefold()
    if writer and reviewer and writer_key == reviewer_key:
        errors.append("author and reviewer must be different execution units")
    if executor and writer and executor_key == writer_key:
        errors.append("executor must be a different execution unit from writer")
    if executor and reviewer and executor_key == reviewer_key:
        errors.append("executor must be a different execution unit from reviewer")
    for role, value in (("writer", writer), ("reviewer", reviewer), ("executor", executor)):
        if value and coordinator_key and value.casefold() == coordinator_key:
            errors.append(f"team.assignments.{role} must not equal the coordinator")

    if delegation_available is False:
        if mode != "single_agent":
            errors.append("delegation unavailable requires team.mode=single_agent")
        if max_agents not in (None, 0):
            errors.append("delegation unavailable requires max_agents=0")
        if max_parallel not in (None, 0):
            errors.append("delegation unavailable requires max_parallel=0")
        if roles:
            errors.append("delegation unavailable requires no delegated roles")

    if risk_level == "low":
        if mode != "single_agent":
            errors.append("low risk must use the single-agent path")
        if max_agents not in (None, 0):
            errors.append("low risk must not create subagents")
        if roles:
            errors.append("low risk must not declare delegated roles")
        if assignments:
            errors.append("low risk must not declare team assignments")
    elif risk_level == "medium":
        if mode != "writer_reviewer":
            errors.append("medium risk requires team.mode=writer_reviewer")
        if max_agents is not None and max_agents > 2:
            errors.append("medium risk allows at most 2 subagents")
        if not {"writer", "reviewer"}.issubset(roles):
            errors.append("medium risk requires writer and reviewer roles")
        for role in ("writer", "reviewer"):
            if role not in assignments:
                errors.append(f"medium risk requires a team.assignments entry for {role}")
        if separated is False:
            errors.append("medium risk requires author-reviewer separation")
    elif risk_level == "high":
        if mode != "full_gate":
            errors.append("high risk requires team.mode=full_gate")
        if max_agents is not None and max_agents != 3:
            errors.append("high risk requires exactly 3 subagent slots in this release")
        if not {"writer", "reviewer", "executor"}.issubset(roles):
            errors.append("high risk requires writer, reviewer, and executor roles")
        for role in ("writer", "reviewer", "executor"):
            if role not in assignments:
                errors.append(f"high risk requires a team.assignments entry for {role}")
        if separated is False:
            errors.append("high risk requires author-reviewer separation")

    return max_agents, assignments


def _validate_write_scope(contract: dict[str, Any], errors: list[str]) -> None:
    paths = _string_list(contract, "write_scope", "write_scope", errors)
    for index, path in enumerate(paths):
        if not _safe_relative_path(path):
            errors.append(
                f"write_scope[{index}] must be a project-relative path without traversal or globs"
            )


def _validate_gates(
    contract: dict[str, Any],
    risk_level: str,
    errors: list[str],
) -> None:
    gates = _mapping(contract, "gates", "gates", errors)
    plan_review = _boolean(gates, "plan_review", "gates.plan_review", errors)
    code_review = _boolean(gates, "code_review", "gates.code_review", errors)
    independent = _boolean(
        gates, "independent_execution", "gates.independent_execution", errors
    )

    if risk_level == "low":
        if plan_review or code_review or independent:
            errors.append("low risk must not require delegated review or execution gates")
    elif risk_level == "medium":
        if code_review is not True:
            errors.append("medium risk requires code_review=true")
        if independent is True:
            errors.append("medium risk uses writer plus reviewer, not a separate executor")
    elif risk_level == "high":
        if plan_review is not True:
            errors.append("high risk requires plan_review=true before writing")
        if code_review is not True:
            errors.append("high risk requires code_review=true")
        if independent is not True:
            errors.append("high risk requires independent_execution=true")


def _validate_acceptance(contract: dict[str, Any], risk_level: str, errors: list[str]) -> None:
    acceptance = contract.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        errors.append("acceptance must be a non-empty list")
        return

    seen_ids: set[str] = set()
    command_count = 0
    for index, item in enumerate(acceptance):
        if not isinstance(item, dict):
            errors.append(f"acceptance[{index}] must be an object")
            continue
        item_id = _string(item, "id", f"acceptance[{index}].id", errors)
        if item_id and item_id in seen_ids:
            errors.append(f"acceptance id duplicated: {item_id}")
        seen_ids.add(item_id)
        _string(item, "criterion", f"acceptance[{index}].criterion", errors)
        method = _string(item, "method", f"acceptance[{index}].method", errors)
        if method and method not in METHODS:
            errors.append(f"acceptance[{index}].method must be command, artifact, or manual")
        command = item.get("command", "")
        if method == "command":
            command_count += 1
            if not isinstance(command, str) or not command.strip():
                errors.append(f"acceptance[{index}].command is required for method=command")
        elif command is not None and not isinstance(command, str):
            errors.append(f"acceptance[{index}].command must be a string when present")
        _string(item, "evidence", f"acceptance[{index}].evidence", errors)

    if risk_level == "high" and command_count == 0:
        errors.append("high risk requires at least one command-based acceptance item")


def _validate_authorization(
    contract: dict[str, Any],
    risk_flags: set[str],
    errors: list[str],
) -> None:
    authorization = _mapping(contract, "authorization", "authorization", errors)
    approval_required = _boolean(
        authorization, "approval_required", "authorization.approval_required", errors
    )
    requested = _string_list(
        authorization,
        "requested_actions",
        "authorization.requested_actions",
        errors,
        allow_empty=True,
    )
    approved = _string_list(
        authorization,
        "approved_actions",
        "authorization.approved_actions",
        errors,
        allow_empty=True,
    )
    stop_before = _boolean(
        authorization, "stop_before_action", "authorization.stop_before_action", errors
    )
    _string(authorization, "note", "authorization.note", errors)

    not_requested = sorted(set(approved) - set(requested))
    if not_requested:
        errors.append(
            "authorization.approved_actions contains actions not present in requested_actions: "
            + ", ".join(not_requested)
        )

    requires_approval = bool(risk_flags & AUTHORIZATION_FLAGS)
    if requires_approval:
        if not requested:
            errors.append("external or irreversible risk requires authorization.requested_actions")
        if approval_required is not True:
            errors.append("external or irreversible risk requires approval_required=true")
        if stop_before is not True:
            errors.append("external or irreversible risk requires stop_before_action=true")

    if approved:
        evidence = authorization.get("user_approval_evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            errors.append(
                "authorization.user_approval_evidence is required when approved_actions is non-empty"
            )


def _validate_budget(contract: dict[str, Any], errors: list[str]) -> None:
    budget = _mapping(contract, "budget", "budget", errors)
    _integer(budget, "max_rounds", "budget.max_rounds", errors, 1, 2)
    agent_timeout = _integer(
        budget,
        "agent_timeout_minutes",
        "budget.agent_timeout_minutes",
        errors,
        1,
        24 * 60,
    )
    total_time = _integer(
        budget,
        "total_time_minutes",
        "budget.total_time_minutes",
        errors,
        1,
        7 * 24 * 60,
    )
    if agent_timeout is not None and total_time is not None and agent_timeout > total_time:
        errors.append("budget.agent_timeout_minutes must not exceed total_time_minutes")
    _integer(
        budget,
        "no_progress_rounds",
        "budget.no_progress_rounds",
        errors,
        1,
        3,
    )
    escalations = _string_list(budget, "escalation", "budget.escalation", errors)
    unknown = sorted(set(escalations) - ESCALATIONS)
    if unknown:
        errors.append("budget.escalation contains unsupported values: " + ", ".join(unknown))


def _validate_evidence_requirements(contract: dict[str, Any], errors: list[str]) -> None:
    requirements = _mapping(
        contract, "evidence_requirements", "evidence_requirements", errors
    )
    keys = (
        "bind_task_id",
        "bind_base_rev",
        "require_artifact_sha256_or_locator",
        "require_command_and_exit_code",
        "require_timestamp",
        "require_raw_output",
        "invalidate_on_artifact_change",
    )
    for key in keys:
        value = _boolean(
            requirements,
            key,
            f"evidence_requirements.{key}",
            errors,
        )
        if value is False:
            errors.append(f"evidence_requirements.{key} must be true")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound_file(
    base_dir: Path,
    relative_path: str,
    expected_sha256: str,
    label: str,
    errors: list[str],
) -> Path | None:
    if not _safe_relative_path(relative_path):
        errors.append(f"{label}.path must be a safe project-relative path")
        return None
    if not SHA256_RE.fullmatch(expected_sha256):
        errors.append(f"{label}.sha256 must be a 64-character SHA256")
        return None
    candidate = (base_dir / relative_path).resolve()
    root = base_dir.resolve()
    if candidate != root and root not in candidate.parents:
        errors.append(f"{label}.path resolves outside the manifest directory")
        return None
    if not candidate.is_file():
        errors.append(f"{label}.path does not exist: {relative_path}")
        return None
    actual = _sha256_file(candidate)
    if actual.lower() != expected_sha256.lower():
        errors.append(f"{label}.sha256 does not match the linked file")
        return None
    return candidate


def _read_linked_text(
    manifest: dict[str, Any],
    key: str,
    base_dir: Path,
    errors: list[str],
) -> str | None:
    record = _mapping(manifest, key, f"manifest.{key}", errors)
    path = _string(record, "path", f"manifest.{key}.path", errors)
    digest = _string(record, "sha256", f"manifest.{key}.sha256", errors)
    if path and digest:
        candidate = _bound_file(base_dir, path, digest, f"manifest.{key}", errors)
        if candidate:
            return candidate.read_text(encoding="utf-8", errors="replace")
    return None


def _require_exact_field(
    fields: dict[str, str],
    key: str,
    expected: str,
    label: str,
    errors: list[str],
) -> None:
    actual = fields.get(key, "")
    if not actual:
        errors.append(f"{label}.{key} is required")
    elif actual != expected:
        errors.append(f"{label}.{key} must equal {expected}")


def _validate_host_evidence(
    contract: dict[str, Any],
    manifest: dict[str, Any],
    base_dir: Path,
    errors: list[str],
) -> None:
    items = manifest.get("host_evidence")
    paths: dict[str, str] = {}
    if not isinstance(items, list) or not items:
        errors.append("manifest.host_evidence must be a non-empty list")
    else:
        for index, item in enumerate(items):
            label = f"manifest.host_evidence[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            kind = _string(item, "kind", f"{label}.kind", errors).lower()
            if kind not in {"detection", "fallback"}:
                errors.append(f"{label}.kind must be detection or fallback")
                continue
            if kind in paths:
                errors.append(f"manifest.host_evidence has duplicate kind: {kind}")
                continue
            path = _string(item, "path", f"{label}.path", errors)
            digest = _string(item, "sha256", f"{label}.sha256", errors)
            if path and digest:
                paths[kind] = path
                _bound_file(base_dir, path, digest, label, errors)

    host = contract.get("host_capabilities", {})
    if not isinstance(host, dict):
        return
    for kind in ("detection", "fallback"):
        if kind not in paths:
            errors.append(f"manifest.host_evidence is missing kind: {kind}")
            continue
        record = host.get(kind, {})
        locator = record.get("evidence", "") if isinstance(record, dict) else ""
        locator_path = locator.split("#", 1)[0].strip() if isinstance(locator, str) else ""
        if not _safe_relative_path(locator_path):
            errors.append(f"host_capabilities.{kind}.evidence must be a safe file locator")
        elif locator_path != paths[kind]:
            errors.append(
                f"host_capabilities.{kind}.evidence must match manifest.host_evidence.{kind}.path"
            )


def _validate_manifest(
    contract: dict[str, Any],
    manifest: Any,
    base_dir: Path,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["evidence manifest JSON must be an object"]

    if manifest.get("manifest_version") != 1 or isinstance(
        manifest.get("manifest_version"), bool
    ):
        errors.append("manifest_version must be integer 1")

    task_id = _string(manifest, "task_id", "manifest.task_id", errors)
    base_rev = _string(manifest, "base_rev", "manifest.base_rev", errors)
    reviewed = _string(
        manifest, "reviewed_revision", "manifest.reviewed_revision", errors
    )
    executed = _string(
        manifest, "executed_revision", "manifest.executed_revision", errors
    )

    if task_id and task_id != contract.get("task_id"):
        errors.append("manifest.task_id must match the task contract")
    if base_rev and base_rev != contract.get("base_rev"):
        errors.append("manifest.base_rev must match the task contract")
    for label, revision in (("reviewed_revision", reviewed), ("executed_revision", executed)):
        if revision and not _bound_revision(revision):
            errors.append(f"manifest.{label} must be an immutable revision")
    if reviewed and executed and reviewed != executed:
        errors.append("reviewed_revision and executed_revision must match")

    handoff_text = _read_linked_text(manifest, "handoff", base_dir, errors)
    if handoff_text is not None:
        handoff_fields = _parse_markdown_fields(
            handoff_text, "manifest.handoff", errors
        )
        _require_exact_field(
            handoff_fields,
            "task_id",
            str(contract.get("task_id", "")),
            "manifest.handoff",
            errors,
        )
        _require_exact_field(
            handoff_fields,
            "reviewed_revision",
            reviewed,
            "manifest.handoff",
            errors,
        )
        state = handoff_fields.get("state", "").casefold()
        if state not in {"approved", "executed"}:
            errors.append("manifest.handoff.state must be approved or executed")

    acceptance_text = _read_linked_text(manifest, "acceptance", base_dir, errors)
    if acceptance_text is not None:
        acceptance_fields = _parse_markdown_fields(
            acceptance_text, "manifest.acceptance", errors
        )
        _require_exact_field(
            acceptance_fields,
            "task_id",
            str(contract.get("task_id", "")),
            "manifest.acceptance",
            errors,
        )
        _require_exact_field(
            acceptance_fields,
            "executed_revision",
            executed,
            "manifest.acceptance",
            errors,
        )
        decision = acceptance_fields.get("decision", "").casefold()
        if decision != "pass":
            errors.append("manifest.acceptance.decision must be pass")

    _validate_host_evidence(contract, manifest, base_dir, errors)

    artifacts = manifest.get("artifacts")
    artifact_hashes: dict[str, str] = {}
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("manifest.artifacts must be a non-empty list")
    else:
        for index, item in enumerate(artifacts):
            if not isinstance(item, dict):
                errors.append(f"manifest.artifacts[{index}] must be an object")
                continue
            path = _string(
                item, "path", f"manifest.artifacts[{index}].path", errors
            )
            digest = _string(
                item, "sha256", f"manifest.artifacts[{index}].sha256", errors
            )
            if path and digest:
                artifact_hashes[path] = digest
                _bound_file(
                    base_dir,
                    path,
                    digest,
                    f"manifest.artifacts[{index}]",
                    errors,
                )

    evidence = manifest.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("manifest.evidence must be a non-empty list")
    else:
        for index, item in enumerate(evidence):
            label = f"manifest.evidence[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            evidence_task = _string(item, "task_id", f"{label}.task_id", errors)
            evidence_rev = _string(item, "base_rev", f"{label}.base_rev", errors)
            author = _string(item, "author", f"{label}.author", errors)
            artifact = _string(item, "artifact", f"{label}.artifact", errors)
            _string(item, "command", f"{label}.command", errors)
            _integer(
                item,
                "exit_code",
                f"{label}.exit_code",
                errors,
                0,
                255,
            )
            _string(item, "timestamp", f"{label}.timestamp", errors)
            _string(item, "scope", f"{label}.scope", errors)
            _string(item, "raw_output", f"{label}.raw_output", errors)
            if evidence_task and evidence_task != contract.get("task_id"):
                errors.append(f"{label}.task_id must match the task contract")
            if evidence_rev and evidence_rev != contract.get("base_rev"):
                errors.append(f"{label}.base_rev must match the task contract")
            if author and _is_placeholder(author):
                errors.append(f"{label}.author must not be a placeholder")
            if artifact and artifact not in artifact_hashes:
                errors.append(f"{label}.artifact must appear in manifest.artifacts")
            digest = item.get("artifact_sha256", "")
            locator = item.get("artifact_locator", "")
            if digest:
                if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                    errors.append(f"{label}.artifact_sha256 must be a 64-character SHA256")
                elif artifact in artifact_hashes and digest.lower() != artifact_hashes[artifact].lower():
                    errors.append(f"{label}.artifact_sha256 does not match manifest.artifacts")
            if not digest:
                if not isinstance(locator, str) or not locator.strip() or _is_placeholder(locator):
                    errors.append(
                        f"{label} requires artifact_sha256 or a non-placeholder artifact_locator"
                    )

    return errors


def validate_manifest(
    contract: dict[str, Any],
    manifest: Any,
    base_dir: Path,
) -> list[str]:
    """Public structural validator for a parsed evidence manifest."""
    return _validate_manifest(contract, manifest, base_dir)


def validate_contract(contract: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["task contract JSON must be an object"]

    version = contract.get("contract_version")
    if version != 1 or isinstance(version, bool):
        errors.append("contract_version must be integer 1")

    task_id = _string(contract, "task_id", "task_id", errors)
    if task_id and not TASK_ID_RE.fullmatch(task_id):
        errors.append("task_id must match [A-Za-z0-9][A-Za-z0-9._:-]{2,127}")
    _string(contract, "task_goal", "task_goal", errors)
    _string_list(contract, "non_goals", "non_goals", errors)

    base_rev = _string(contract, "base_rev", "base_rev", errors)
    if base_rev and not _bound_revision(base_rev):
        errors.append("base_rev must be an immutable hash or prefixed immutable revision")

    level, risk_flags = _validate_risk(contract, errors)
    delegation_available = _validate_host(contract, errors)
    _validate_team(contract, level, delegation_available, errors)
    _validate_write_scope(contract, errors)
    _validate_gates(contract, level, errors)
    _validate_acceptance(contract, level, errors)
    _validate_authorization(contract, risk_flags, errors)
    _validate_budget(contract, errors)
    _validate_evidence_requirements(contract, errors)

    if delegation_available is False:
        gates = contract.get("gates")
        if isinstance(gates, dict) and any(value is True for value in gates.values()):
            errors.append("delegation unavailable requires delegated gates to be false")

    return errors


def _parse_json_block(text: str, label: str) -> tuple[Any | None, list[str]]:
    blocks = JSON_BLOCK_RE.findall(text)
    if len(blocks) != 1:
        return None, [f"expected exactly one fenced json block in {label}, found {len(blocks)}"]
    try:
        return json.loads(blocks[0]), []
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON in {label}: {exc.msg} at line {exc.lineno} column {exc.colno}"]


def parse_contract_text(text: str) -> tuple[Any | None, list[str]]:
    return _parse_json_block(text, "task contract")


def parse_manifest_text(text: str) -> tuple[Any | None, list[str]]:
    return _parse_json_block(text, "evidence manifest")


def validate_text(text: str) -> list[str]:
    contract, errors = parse_contract_text(text)
    if errors:
        return errors
    return validate_contract(contract)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate task-contract structure and linked evidence hashes. This is not a semantic proof."
    )
    parser.add_argument("path", help="Markdown file containing one fenced json block")
    parser.add_argument(
        "--manifest",
        help="Optional Markdown evidence manifest containing one fenced json block",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    args = parser.parse_args(argv)

    path = Path(args.path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        payload = {"ok": False, "errors": [f"cannot read {path}: {exc}"]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=True))
        else:
            print(f"STRUCTURAL VALIDATION FAILED: {payload['errors'][0]}")
        return 2

    contract, errors = parse_contract_text(text)
    if not errors:
        errors = validate_contract(contract)
    manifest_path: Path | None = None
    if args.manifest and not errors:
        manifest_path = Path(args.manifest)
        try:
            manifest_text = manifest_path.read_text(encoding="utf-8")
        except OSError as exc:
            payload = {"ok": False, "errors": [f"cannot read {manifest_path}: {exc}"]}
            if args.json:
                print(json.dumps(payload, ensure_ascii=True))
            else:
                print(f"STRUCTURAL VALIDATION FAILED: {payload['errors'][0]}")
            return 2
        manifest, manifest_errors = parse_manifest_text(manifest_text)
        errors.extend(manifest_errors)
        if not manifest_errors:
            errors.extend(validate_manifest(contract, manifest, manifest_path.parent))

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not errors,
                    "errors": errors,
                    "manifest_checked": manifest_path is not None,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
    elif errors:
        print("STRUCTURAL VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
    else:
        print("STRUCTURAL VALIDATION PASSED")
        print(
            "This result checks structure and linked-file hashes only; "
            "it does not prove reviewer independence, command execution, or semantic correctness."
        )
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
