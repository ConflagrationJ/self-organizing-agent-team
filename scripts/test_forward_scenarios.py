#!/usr/bin/env python3
"""Structural fixtures for the two README forward scenarios.

This does not instantiate agents and does not prove behavioral compliance.
"""

from __future__ import annotations

import sys

from test_validate_task_contract import (
    high_risk_contract,
    low_risk_contract,
    medium_risk_contract,
    render,
)
from validate_task_contract import validate_text


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    low = low_risk_contract()
    medium = medium_risk_contract()
    high = high_risk_contract()

    for label, contract in (("low", low), ("medium", medium), ("high", high)):
        errors = validate_text(render(contract))
        require(not errors, f"{label} fixture failed validation: {errors}")

    require(low["team"]["max_agents"] == 0, "low-risk fixture must create no subagents")
    require(low["team"]["roles"] == [], "low-risk fixture must declare no delegated roles")
    require(not any(low["gates"].values()), "low-risk fixture must not require delegated gates")

    require(high["team"]["max_agents"] == 3, "high-risk fixture must reserve three subagents")
    require(high["gates"]["plan_review"], "high-risk fixture requires plan review")
    require(high["gates"]["code_review"], "high-risk fixture requires code review")
    require(
        high["gates"]["independent_execution"],
        "high-risk fixture requires independent execution",
    )
    require(
        bool(set(high["risk"]["flags"]) & {"network", "delete", "state_migration"}),
        "high-risk fixture must include external, destructive, or migration risk",
    )
    require(
        high["authorization"]["approval_required"],
        "high-risk fixture must require explicit approval",
    )

    assignments = high["team"]["assignments"]
    require(
        len({assignments["writer"], assignments["reviewer"], assignments["executor"]}) == 3,
        "writer, reviewer, and executor must be distinct",
    )

    print("FORWARD STRUCTURE FIXTURES PASSED")
    print("This is not a behavioral forward test; no agents were created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
