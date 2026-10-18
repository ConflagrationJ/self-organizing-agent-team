#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Tuple


SCRIPT = Path(__file__).with_name("host_preflight.py")
SPEC = importlib.util.spec_from_file_location("host_preflight", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class HostPreflightTests(unittest.TestCase):
    def build_host(
        self,
        *,
        model: str = "deepseek-flash",
        provider_id: str = "custom",
        provider_name: Optional[str] = "custom",
        include_provider: bool = True,
        include_model_provider: bool = True,
        base_url: str = "https://api.deepseek.com",
        requires_auth: bool = False,
        catalog_version: Optional[str] = "v2",
        feature_v2: bool = False,
        collab: Optional[bool] = None,
        agents_enabled: Optional[bool] = None,
        session_version: Optional[str] = "v2",
    ) -> Tuple[Path, Optional[Path]]:
        tmp = tempfile.TemporaryDirectory(prefix="sot-preflight-")
        root = Path(tmp.name)
        self.addCleanup(tmp.cleanup)

        lines = []
        if include_model_provider:
            lines.append(f'model_provider = "{provider_id}"')
        lines.extend(
            [
                f'model = "{model}"',
                'model_catalog_json = "cc-switch-model-catalog.json"',
            ]
        )
        if include_provider:
            lines.extend(["", f"[model_providers.{provider_id}]"])
            if provider_name is not None:
                lines.append(f'name = "{provider_name}"')
            lines.extend(
                [
                    f'base_url = "{base_url}"',
                    f"requires_openai_auth = {str(requires_auth).lower()}",
                ]
            )
        lines.extend(
            [
                "",
                "[features]",
                f"multi_agent_v2 = {str(feature_v2).lower()}",
            ]
        )
        if collab is not None:
            lines.append(f"multi_agent = {str(collab).lower()}")
        if agents_enabled is not None:
            lines.extend(["", "[agents]", f"enabled = {str(agents_enabled).lower()}"])

        (root / "config.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")

        entry = {"slug": model}
        if catalog_version:
            entry["multi_agent_version"] = catalog_version
        (root / "cc-switch-model-catalog.json").write_text(
            json.dumps({"models": [entry]}), encoding="utf-8"
        )

        session_path = None
        if session_version:
            session_path = root / "sessions" / "2026" / "10" / "18" / "session.jsonl"
            session_path.parent.mkdir(parents=True)
            session_path.write_text(
                json.dumps(
                    {
                        "multi_agent_version": session_version,
                        "cli_version": "test-cli",
                    }
                ),
                encoding="utf-8",
            )
        return root, session_path

    def test_v2_custom_provider_routes_single_agent(self):
        root, session = self.build_host()
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["provider_kind"], "non_openai")
        self.assertEqual(result["route"], "single_agent")
        self.assertEqual(result["predicted_multi_agent_version"], "v2")

    def test_non_openai_v2_can_opt_into_probe(self):
        root, session = self.build_host()
        result = MOD.inspect_host(root, session, allow_probe=True)
        self.assertTrue(result["probe_override"])
        self.assertEqual(result["route"], "v2_probe")

    def test_custom_provider_pointed_at_openai_host_is_still_non_openai(self):
        root, session = self.build_host(base_url="https://api.openai.com/v1")
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["base_url_kind"], "openai_host")
        self.assertEqual(result["provider_kind"], "non_openai")
        self.assertEqual(result["route"], "single_agent")

    def test_v2_local_proxy_registered_as_custom_routes_single_agent(self):
        root, session = self.build_host(
            base_url="http://127.0.0.1:15721/v1",
            requires_auth=True,
        )
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["base_url_kind"], "local_proxy")
        self.assertEqual(result["provider_kind"], "non_openai")
        self.assertEqual(result["route"], "single_agent")

    def test_v2_openai_provider_requires_probe(self):
        root, session = self.build_host(
            provider_id="openai",
            include_provider=False,
            catalog_version="v2",
        )
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["provider_id"], "openai")
        self.assertEqual(result["provider_name"], "OpenAI")
        self.assertEqual(result["provider_kind"], "openai")
        self.assertEqual(result["route"], "v2_probe")

    def test_missing_model_provider_defaults_to_openai(self):
        root, session = self.build_host(
            include_model_provider=False,
            include_provider=False,
            catalog_version="v2",
        )
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["provider_id"], "openai")
        self.assertEqual(result["provider_name"], "OpenAI")
        self.assertEqual(result["route"], "v2_probe")

    def test_provider_named_openai_on_local_proxy_requires_probe(self):
        root, session = self.build_host(
            provider_name="OpenAI",
            base_url="http://127.0.0.1:15721/v1",
            requires_auth=True,
            catalog_version="v2",
        )
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["provider_kind"], "openai")
        self.assertEqual(result["base_url_kind"], "local_proxy")
        self.assertEqual(result["route"], "v2_probe")

    def test_lowercase_openai_name_is_not_openai(self):
        root, session = self.build_host(
            provider_name="openai",
            base_url="https://api.openai.com/v1",
            catalog_version="v2",
        )
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["provider_kind"], "non_openai")
        self.assertEqual(result["route"], "single_agent")

    def test_catalog_v1_routes_v1(self):
        root, session = self.build_host(catalog_version="v1", session_version="v1")
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["route"], "v1")
        self.assertEqual(result["predicted_multi_agent_version"], "v1")

    def test_feature_switch_wins_over_catalog(self):
        root, session = self.build_host(
            provider_id="openai",
            include_provider=False,
            catalog_version="v1",
            feature_v2=True,
            session_version="v2",
        )
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["config_multi_agent_source"], "feature")
        self.assertEqual(result["predicted_multi_agent_version"], "v2")
        self.assertEqual(result["route"], "v2_probe")

    def test_stale_v2_session_with_config_v1_requires_restart(self):
        root, session = self.build_host(catalog_version="v1", session_version="v2")
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["route"], "restart_required")

    def test_observed_v1_with_config_v2_routes_v1_and_recommends_restart(self):
        root, session = self.build_host(catalog_version="v2", session_version="v1")
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["effective_multi_agent_version"], "v1")
        self.assertTrue(result["config_mismatch"])
        self.assertTrue(result["restart_recommended"])
        self.assertEqual(result["route"], "v1")

    def test_missing_catalog_uses_session_observation(self):
        root, session = self.build_host(catalog_version=None, session_version="v2")
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["prediction_source"], "session")
        self.assertEqual(result["predicted_multi_agent_version"], "v2")
        self.assertEqual(result["route"], "single_agent")

    def test_agents_disabled_routes_single_agent(self):
        root, session = self.build_host(
            provider_id="openai",
            include_provider=False,
            agents_enabled=False,
            session_version=None,
        )
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["config_multi_agent_version"], "disabled")
        self.assertEqual(result["effective_multi_agent_version"], "disabled")
        self.assertEqual(result["route"], "single_agent")
        self.assertIn("disabled", result["reason"])

    def test_collab_disabled_without_catalog_routes_single_agent(self):
        root, session = self.build_host(
            provider_id="openai",
            include_provider=False,
            catalog_version=None,
            collab=False,
            session_version=None,
        )
        result = MOD.inspect_host(root, session)
        self.assertEqual(result["config_multi_agent_version"], "disabled")
        self.assertEqual(result["route"], "single_agent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
