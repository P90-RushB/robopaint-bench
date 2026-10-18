"""Offline capability checks against a small public OpenRouter metadata snapshot."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent_ark.agent.api_agent import APIAgent
from agent_ark.agent.simple_agent.runtime import SimpleRuntimeConfig
from agent_ark.ark_eval.run_api_agent import load_eval_config


ROOT = Path(__file__).resolve().parents[1]
SLUGS = {"qwen": "qwen/qwen3.8-max-prime", "kimi": "moonshotai/kimi-k3", "mimo": "xiaomi/mimo-v2.6-pro"}


class OpenRouterProfileTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((ROOT / "benchmarks/openrouter-model-capabilities-20261019.json").read_text("utf-8"))
        self.capabilities = {item["profile_name"]: item for item in self.snapshot["models"]}
        self.configs = {case: load_eval_config(str(ROOT / "benchmarks" / case / "eval.yaml"))
                        for case in ("golden_gate", "pelican")}
        for guard in (patch.object(socket.socket, "connect", side_effect=AssertionError("No network in profile tests")),
                      patch.object(subprocess, "Popen", side_effect=AssertionError("No Player/process in profile tests"))):
            guard.start()
            self.addCleanup(guard.stop)

    def test_both_cases_offer_same_three_portable_model_profiles(self):
        comparable = []
        for case, config in self.configs.items():
            models = config["models"]
            self.assertEqual(len(models), len({item["name"] for item in models}))
            selected = {item["name"]: deepcopy(item) for item in models if item["name"] in SLUGS}
            self.assertEqual(set(SLUGS), set(selected))
            for name, item in selected.items():
                self.assertEqual(SLUGS[name], item["model"])
                self.assertEqual("simple", item["agent_type"])
                self.assertEqual("openrouter", item["provider"])
                self.assertEqual("https://openrouter.ai/api/v1", item["base_url"])
                self.assertEqual("OPENROUTER_API_KEY", item["api_key_env"])
                self.assertEqual(f"runs/{case}/workspaces", item["simple_agent"]["tools"].pop("workspace_parent"))
                self.assertNotIn("provider", item["simple_agent"])
            comparable.append(selected)
        self.assertEqual(*comparable)

    def test_highest_published_reasoning_option_and_real_request_mapping(self):
        for name, capability in self.capabilities.items():
            model = next(item for item in self.configs["golden_gate"]["models"] if item["name"] == name)
            efforts = capability["reasoning"].get("supported_efforts")
            effort = model.get("reasoning_effort")
            if efforts:
                self.assertEqual(efforts[0], effort, "OpenRouter lists supported efforts highest first")
                self.assertIn("reasoning_effort", capability["supported_parameters"])
            else:
                self.assertNotIn("supported_efforts", capability["reasoning"])
                self.assertNotIn("reasoning_effort", capability["supported_parameters"])
                self.assertIsNone(effort, "Do not invent a MiMo max effort unsupported by its metadata")
                self.assertEqual({"type": "enabled"}, model["thinking"])
            source = SimpleNamespace(client=SimpleNamespace(provider="openrouter"),
                thinking_type=APIAgent._normalize_thinking_type(model.get("thinking")),
                reasoning_effort=APIAgent._normalize_reasoning_effort(effort))
            body, top_level_effort = APIAgent._request_parameters(source)
            expected = {"enabled": True}
            if effort is not None:
                expected["effort"] = effort
            self.assertEqual({"reasoning": expected}, body)
            self.assertIsNone(top_level_effort)

    def test_native_tools_and_image_inputs_have_a_compatible_endpoint(self):
        defaults = SimpleRuntimeConfig()
        for name, capability in self.capabilities.items():
            model = next(item for item in self.configs["golden_gate"]["models"] if item["name"] == name)
            self.assertIn("image", capability["architecture"]["input_modalities"])
            self.assertEqual(["text"], capability["architecture"]["output_modalities"])
            required = {"tools", "tool_choice", "reasoning", "max_tokens"}
            if model.get("reasoning_effort") is not None:
                required.add("reasoning_effort")
            choice = model["simple_agent"]["tool_choice"]
            compatible = [endpoint for endpoint in capability["provider_endpoints"]
                if required <= set(endpoint["supported_parameters"])
                and endpoint["supports_tool_choice"].get(choice) is True
                and endpoint["context_length"] >= defaults.max_context_tokens
                and endpoint["max_completion_tokens"] >= max(model["max_completion_tokens"], defaults.summary_output_tokens)]
            self.assertTrue(compatible, f"No published endpoint supports {name}'s tools/effort/token limits")
        qwen = self.capabilities["qwen"]["provider_endpoints"]
        self.assertTrue(all(item["supports_tool_choice"]["required"] is False for item in qwen))
        self.assertEqual("auto", next(item for item in self.configs["golden_gate"]["models"] if item["name"] == "qwen")["simple_agent"]["tool_choice"])

    def test_profiles_preserve_task_and_simple_agent_budgets(self):
        for config in self.configs.values():
            env = config["env_cfg"]["env_config_overrides"]
            self.assertEqual((3, 96, 960, 720), (env["max_attempts"], env["max_steps_per_attempt"], env["width"], env["height"]))
            self.assertEqual(("fixed", "fixed", "infinite", 480), tuple(env["task_params"][key]
                for key in ("brush_mode", "board_mode", "pigment_mode", "physics_frequency_hz")))
            for model in config["models"]:
                if model["name"] not in SLUGS:
                    continue
                self.assertEqual(20480, model["max_completion_tokens"])
                self.assertIsNone(model["temperature"])
                self.assertEqual(0, model["max_retries"])
                self.assertEqual(1800, model["timeout_s"])
                self.assertEqual("max_tokens", model["simple_agent"]["output_token_parameter"])
                self.assertNotIn("context", model["simple_agent"])
                self.assertNotIn("limits", model["simple_agent"]["tools"])
                self.assertTrue(model["simple_agent"]["tools"]["enabled"])


if __name__ == "__main__":
    unittest.main()
