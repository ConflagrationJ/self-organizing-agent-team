#!/usr/bin/env python3
"""Report the local Codex delegation route without changing configuration.

The skill uses this preflight to avoid spawning a child on a host that is
known to lose the child task body. It reads only config.toml, the referenced
model catalog, and the latest session file.

Route semantics:
  v1                the running session or effective configuration selects V1
  v2_probe          V2 on the built-in OpenAI provider; run the round-trip probe
  single_agent      no delegation: V2 on a non-OpenAI provider, or agents disabled
  restart_required  the running session is V2 but the current config selects V1
  probe             the effective version cannot be determined

The provider test mirrors the host runtime: Codex treats a provider as OpenAI
only when ModelProviderInfo::is_openai() is true, and that method compares the
configured provider name with "OpenAI". A base URL is not the test, so an
api.openai.com URL under a custom provider id is still non-OpenAI, and a local
proxy registered under a custom provider id is non-OpenAI too.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional


SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
KV_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*(.+?)\s*$")

OPENAI_PROVIDER_ID = "openai"
OPENAI_PROVIDER_NAME = "OpenAI"


def _strip_comment(line: str) -> str:
    """Remove a TOML comment while preserving # inside quoted strings."""
    quote: Optional[str] = None
    escaped = False
    out = []
    for char in line:
        if escaped:
            out.append(char)
            escaped = False
            continue
        if char == "\\" and quote == '"':
            out.append(char)
            escaped = True
            continue
        if quote:
            out.append(char)
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            out.append(char)
            continue
        if char == "#":
            break
        out.append(char)
    return "".join(out)


def _parse_value(raw: str) -> Any:
    value = raw.strip()
    if value == "true":
        return True
    if value == "false":
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_config(text: str) -> Dict[str, Dict[str, Any]]:
    sections: Dict[str, Dict[str, Any]] = {"root": {}}
    current = sections["root"]
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        section_match = SECTION_RE.match(line)
        if section_match:
            name = section_match.group(1).strip()
            current = sections.setdefault(name, {})
            continue
        kv_match = KV_RE.match(line)
        if kv_match:
            current[kv_match.group(1)] = _parse_value(kv_match.group(2))
    return sections


def latest_session(codex_home: Path) -> Optional[Path]:
    sessions = codex_home / "sessions"
    if not sessions.exists():
        return None
    files = list(sessions.rglob("*.jsonl"))
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _session_values(session_path: Optional[Path]) -> Dict[str, Optional[str]]:
    if session_path is None or not session_path.exists():
        return {"multi_agent_version": None, "cli_version": None}
    try:
        with session_path.open("r", encoding="utf-8", errors="ignore") as handle:
            text = handle.read(2_000_000)
    except OSError:
        return {"multi_agent_version": None, "cli_version": None}

    version_matches = re.findall(
        r'"multi_agent_version"\s*:\s*"(v[12]|disabled)"', text
    )
    cli_matches = re.findall(r'"cli_version"\s*:\s*"([^"]+)"', text)
    return {
        "multi_agent_version": version_matches[-1] if version_matches else None,
        "cli_version": cli_matches[-1] if cli_matches else None,
    }


def _find_catalog_model(catalog: Any, model: str) -> Optional[Dict[str, Any]]:
    if not isinstance(catalog, dict):
        return None
    models = catalog.get("models", [])
    if not isinstance(models, list):
        return None
    for entry in models:
        if not isinstance(entry, dict):
            continue
        if entry.get("slug") == model or entry.get("display_name") == model:
            return entry
    return None


def _base_url_kind(base_url: str) -> str:
    """Describe the endpoint for diagnostics only; do not route on it."""
    lower = base_url.lower()
    if "api.openai.com" in lower:
        return "openai_host"
    if "127.0.0.1" in lower or "localhost" in lower or "[::1]" in lower:
        return "local_proxy"
    if lower:
        return "remote"
    return "unset"


def _resolve_provider(
    root: Dict[str, Any],
    sections: Dict[str, Dict[str, Any]],
) -> tuple[str, str, Dict[str, Any]]:
    provider_id = str(root.get("model_provider") or OPENAI_PROVIDER_ID)
    provider = sections.get(f"model_providers.{provider_id}", {})
    configured_name = provider.get("name")
    if isinstance(configured_name, str) and configured_name:
        provider_name = configured_name
    elif provider_id == OPENAI_PROVIDER_ID:
        provider_name = OPENAI_PROVIDER_NAME
    else:
        provider_name = provider_id
    return provider_id, provider_name, provider


def inspect_host(
    codex_home: Path,
    session_path: Optional[Path] = None,
    allow_probe: bool = False,
) -> Dict[str, Any]:
    config_path = codex_home / "config.toml"
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    sections = parse_config(config_text)
    root = sections.get("root", {})
    model = str(root.get("model", ""))
    provider_id, provider_name, provider = _resolve_provider(root, sections)
    is_openai_provider = provider_name == OPENAI_PROVIDER_NAME

    feature_section = sections.get("features", {})
    feature_v2 = feature_section.get("multi_agent_v2")
    feature_table = sections.get("features.multi_agent_v2", {}).get("enabled")
    if feature_table is not None:
        feature_v2 = feature_table

    collab_feature = feature_section.get("multi_agent")
    collab_table = sections.get("features.multi_agent", {}).get("enabled")
    collab = collab_table if collab_table is not None else collab_feature

    agents_value = sections.get("agents", {}).get("enabled")
    agents_enabled = True if agents_value is None else agents_value is not False

    catalog_path: Optional[Path] = None
    catalog_version: Optional[str] = None
    catalog_json = root.get("model_catalog_json")
    if isinstance(catalog_json, str) and catalog_json:
        candidate = Path(catalog_json)
        catalog_path = candidate if candidate.is_absolute() else codex_home / candidate
        if catalog_path.exists():
            try:
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                catalog = None
            entry = _find_catalog_model(catalog, model)
            if entry:
                version = entry.get("multi_agent_version")
                catalog_version = str(version) if version else None

    session_path = session_path or latest_session(codex_home)
    session = _session_values(session_path)
    observed = session["multi_agent_version"]

    config_version: Optional[str] = None
    config_source: Optional[str] = None
    if feature_v2 is True:
        config_version = "v2"
        config_source = "feature"
    elif agents_enabled is False:
        config_version = "disabled"
        config_source = "agents.enabled"
    elif catalog_version in {"v1", "v2", "disabled"}:
        config_version = catalog_version
        config_source = "catalog"
    elif collab is False:
        config_version = "disabled"
        config_source = "feature"

    if config_version in {"v1", "v2", "disabled"}:
        predicted = config_version
    elif observed in {"v1", "v2", "disabled"}:
        predicted = observed
    else:
        predicted = "v1"

    if observed in {"v1", "v2"}:
        effective = observed
    elif config_version in {"v1", "v2", "disabled"}:
        effective = config_version
    else:
        effective = "v1"

    config_mismatch = bool(
        config_version in {"v1", "v2", "disabled"}
        and observed in {"v1", "v2", "disabled"}
        and config_version != observed
    )
    restart_recommended = bool(
        config_mismatch and config_version == "v2" and effective == "v1"
    )

    base_url = str(provider.get("base_url", ""))
    requires_auth = provider.get("requires_openai_auth")
    base_url_kind = _base_url_kind(base_url)

    if config_version == "v1" and observed == "v2":
        route = "restart_required"
        reason = (
            "the running session is V2 but the current config selects V1; "
            "start a new chat to apply V1"
        )
    elif effective == "disabled":
        route = "single_agent"
        reason = "multi-agent is disabled by config; do not assume delegation tools exist"
    elif effective == "v1":
        route = "v1"
        reason = "the running session or effective configuration selects V1"
    elif effective == "v2" and not is_openai_provider and not allow_probe:
        route = "single_agent"
        reason = (
            "V2 is selected on a non-OpenAI provider; the runtime is expected "
            "to drop child task bodies because the provider name is not OpenAI"
        )
    elif effective == "v2":
        route = "v2_probe"
        if is_openai_provider:
            reason = "V2 is selected on the OpenAI provider; a round-trip probe is required"
        else:
            reason = (
                "V2 is selected on a non-OpenAI provider and --probe was requested; "
                "the round-trip probe decides for this host build"
            )
    else:
        route = "probe"
        reason = "the effective version is not clear; run the probe"

    if restart_recommended:
        reason += (
            "; the config now selects V2 but this session is still V1, so "
            "restart after the current task to apply it"
        )

    return {
        "model": model,
        "provider": provider_id,
        "provider_id": provider_id,
        "provider_name": provider_name,
        "provider_kind": "openai" if is_openai_provider else "non_openai",
        "is_openai_provider": is_openai_provider,
        "base_url": base_url,
        "base_url_kind": base_url_kind,
        "requires_openai_auth": requires_auth,
        "agents_enabled": agents_enabled,
        "feature_multi_agent_v2": feature_v2,
        "feature_multi_agent": collab,
        "catalog_multi_agent_version": catalog_version,
        "config_multi_agent_version": config_version,
        "config_multi_agent_source": config_source,
        "latest_session_multi_agent_version": observed,
        "cli_version": session["cli_version"],
        "predicted_multi_agent_version": predicted,
        "effective_multi_agent_version": effective,
        "prediction_source": config_source or ("session" if observed else "default"),
        "probe_override": allow_probe,
        "config_mismatch": config_mismatch,
        "restart_recommended": restart_recommended,
        "route": route,
        "reason": reason,
        "catalog_file": str(catalog_path) if catalog_path else None,
        "session_file": str(session_path) if session_path else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-home",
        default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")),
    )
    parser.add_argument("--session", default=None)
    parser.add_argument(
        "--probe",
        action="store_true",
        help="run the probe even when V2 is selected on a non-OpenAI provider",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = inspect_host(
        Path(args.codex_home).expanduser(),
        Path(args.session).expanduser() if args.session else None,
        allow_probe=args.probe,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for key in (
            "model",
            "provider_id",
            "provider_name",
            "provider_kind",
            "is_openai_provider",
            "base_url",
            "base_url_kind",
            "requires_openai_auth",
            "agents_enabled",
            "feature_multi_agent_v2",
            "feature_multi_agent",
            "catalog_multi_agent_version",
            "config_multi_agent_version",
            "config_multi_agent_source",
            "latest_session_multi_agent_version",
            "cli_version",
            "predicted_multi_agent_version",
            "effective_multi_agent_version",
            "prediction_source",
            "probe_override",
            "config_mismatch",
            "restart_recommended",
            "route",
            "reason",
            "catalog_file",
            "session_file",
        ):
            print(f"{key}: {result.get(key)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
