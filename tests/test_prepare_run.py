"""Offline integration checks; no Player, model client, or network is permitted."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import yaml

from agent_ark.agent.simple_agent.runtime import SimpleRuntimeConfig
from agent_ark.agent.simple_agent.tools import ToolLimits
# Import before the process guard: NumPy can run a Windows version probe.
from agent_ark.ark_eval.run_api_agent import load_eval_config

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_run", ROOT / "scripts/prepare_run.py")
prepare_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_run)


class OfflinePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="robopaint-config-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "checkout with spaces"
        self.repo.mkdir()
        self.player = self.root / "player"
        self.player.mkdir()
        self.executable = self.player / "AgentArk.x86_64"
        self.executable.write_bytes(b"offline fixture - never execute")
        self.mods = self.player / "AgentArk_Data/Resources/Mods"
        self.mods.mkdir(parents=True)
        self.store = self.root / "separate task store"
        self.task = self.store / "RobotPainting"
        (self.task / "cfg").mkdir(parents=True)
        (self.task / "dll").mkdir()
        (self.task / "dll/RobotPainting.dll").write_bytes(b"offline fixture")
        (self.task / "catalog_1.0.json").write_text("{}\n", encoding="utf-8")
        (self.task / "scene.bundle").write_bytes(b"offline addressables fixture")
        (self.task / "References").mkdir()
        image = self.task / "References/GoldenGateBridge_reference.png"
        with Image.new("RGB", (64, 40), (30, 140, 210)) as pixels:
            pixels.save(image)
        self.lock = json.loads((ROOT / "benchmarks/versions.json").read_text("utf-8"))
        self.lock["reference_images"][image.name]["sha256"] = prepare_run.sha256(image)
        for case in prepare_run.CASES:
            directory = self.repo / "benchmarks" / case
            directory.mkdir(parents=True)
            for filename in ("eval.yaml", "painting_goal.txt"):
                (directory / filename).write_bytes((ROOT / "benchmarks" / case / filename).read_bytes())
        # Minimal task fixture with inheritance that the benchmark must retain.
        task_cfg = {"task_name": "RobotPainting", "task_info": {"id": 107, "name": "RobotPainting"},
                    "max_attempts": 3, "max_steps_per_attempt": 96,
                    "task_params": {"reference_mode": "image", "reference_filenames": [image.name],
                                    "randomized_board_rejection_limit": 64},
                    "env_wrapper_cfg": {"context_manager": {"messages": {"enabled": True, "text_max_chars": 32768}}}}
        self.task_cfg = self.task / "cfg/task_config.yaml"
        self.task_cfg.write_text(yaml.safe_dump(task_cfg), encoding="utf-8")
        runtime_manifest = self.repo / "benchmarks" / self.lock["task"]["runtime_file_manifests"]["linux"]["filename"]
        runtime_manifest.write_text(json.dumps({"files": prepare_run.tree_manifest(self.task)}), encoding="utf-8")
        (self.repo / "benchmarks/versions.json").write_text(json.dumps(self.lock), encoding="utf-8")
        baseline = {"task_name": "OldTask", "width": 84, "height": 84, "obs_mode": "decision",
                    "engine_para": {"time_scale": 1}, "task_params": {"stale_other_task": True},
                    "env_wrapper_cfg": {}}
        self.baseline = self.mods / "config.yaml.bak"
        self.baseline.write_text(yaml.safe_dump(baseline), encoding="utf-8")
        (self.mods / "config.yaml").write_text("task_name: OtherRunningTask\n", encoding="utf-8")
        self.before = {path: path.read_bytes() for directory in (self.mods, self.store)
                       for path in directory.rglob("*") if path.is_file()}
        identity = {"commit": self.lock["agentark"]["commit"], "source_dirty": False,
                    "matches_version_lock": True, "context_defaults": asdict(SimpleRuntimeConfig()),
                    "tool_limits_defaults": asdict(ToolLimits(max_records=512))}
        for guard in (patch.object(prepare_run, "ROOT", self.repo),
                      patch.object(prepare_run, "agentark_identity", return_value=identity),
                      patch("subprocess.Popen", side_effect=AssertionError("Preparation must not launch processes")),
                      patch.object(socket.socket, "connect", side_effect=AssertionError("Preparation must not use the network"))):
            guard.start()
            self.addCleanup(guard.stop)

    def args(self, case="golden_gate", model="sol", output="run", extra=()):
        return prepare_run.parser().parse_args([
            "--case", case, "--model", model, "--env-path", str(self.executable),
            "--mod-path", str(self.mods), "--task-store", str(self.store),
            "--output-dir", str(self.root / output), *extra])

    def assert_template_unchanged(self):
        self.assertEqual(self.before, {path: path.read_bytes() for directory in (self.mods, self.store)
                                      for path in directory.rglob("*") if path.is_file()})

    def test_both_cases_use_real_agentark_loader_and_merger(self):
        for case, model, count in (("golden_gate", "sol", 1), ("pelican", "argon", 0)):
            with self.subTest(case=case):
                path = prepare_run.prepare(self.args(case, model, case))
                cfg = load_eval_config(str(path))
                self.assertEqual([model], [entry["name"] for entry in cfg["models"]])
                self.assertNotIn("context", cfg["models"][0]["simple_agent"])
                self.assertNotIn("limits", cfg["models"][0]["simple_agent"]["tools"])
                env, hashes = prepare_run.offline_contract(path, self.baseline, self.task_cfg)
                self.assertEqual((3, 96, 960, 720), (env["max_attempts"], env["max_steps_per_attempt"], env["width"], env["height"]))
                self.assertEqual(480, env["task_params"]["physics_frequency_hz"])
                self.assertEqual("image" if count else "text", env["task_params"]["reference_mode"])
                self.assertNotIn("mode", env["task_params"])
                self.assertEqual(64, env["task_params"]["randomized_board_rejection_limit"])
                self.assertNotIn("stale_other_task", env["task_params"])
                self.assertEqual(count, len(hashes))
                self.assertEqual(32768, env["env_wrapper_cfg"]["context_manager"]["messages"]["text_max_chars"])
                self.assertTrue(env["env_wrapper_cfg"]["context_manager"]["messages"]["include_images"])
                self.assertTrue(Path(cfg["eval"]["output_path"]).is_absolute())
                record = json.loads((path.parent / "manifest.json").read_text("utf-8"))
                self.assertFalse(record["custom_target"])
                self.assertTrue(record["preparation_only"])
                self.assertEqual(32768, record["agentark"]["context_defaults"]["summary_output_tokens"])
        self.assert_template_unchanged()

    def test_custom_two_image_goal_is_copied_in_order(self):
        goal = self.root / "my_goal.txt"
        goal.write_text("Paint the person from image 1 against the landscape in image 2.\n", encoding="utf-8")
        images = []
        for name, color in (("person.png", "red"), ("background.jpg", "blue")):
            image = self.root / name
            with Image.new("RGB", (32, 24), color) as pixels:
                pixels.save(image)
            images.append(image)
        extra = ("--goal-file", str(goal), "--reference-image", str(images[0]), "--reference-image", str(images[1]))
        path = prepare_run.prepare(self.args(extra=extra))
        cfg = load_eval_config(str(path))
        params = cfg["env_cfg"]["env_config_overrides"]["task_params"]
        self.assertEqual([image.name for image in images], params["reference_filenames"])
        self.assertEqual(goal.read_bytes(), (path.parent / "inputs/painting_goal.txt").read_bytes())
        for image in images:
            self.assertEqual(image.read_bytes(), (path.parent / "inputs" / image.name).read_bytes())
        manifest = json.loads((path.parent / "manifest.json").read_text("utf-8"))
        self.assertTrue(manifest["custom_target"])
        self.assertEqual([prepare_run.sha256(image) for image in images], manifest["reference_sha256"])
        self.assertTrue(cfg["eval"]["cases"][0]["case_id"].startswith("custom-"))
        self.assert_template_unchanged()

    def test_text_only_can_override_an_image_case_without_stale_attachment(self):
        goal = self.root / "goal.txt"
        goal.write_text("Paint a lighthouse.\n", encoding="utf-8")
        path = prepare_run.prepare(self.args(extra=("--goal-file", str(goal), "--text-only")))
        env, hashes = prepare_run.offline_contract(path, self.baseline, self.task_cfg)
        self.assertEqual("text", env["task_params"]["reference_mode"])
        self.assertEqual([], env["task_params"]["reference_filenames"])
        self.assertEqual([], hashes)
        self.assert_template_unchanged()

    def test_reusing_a_run_cannot_overwrite_records(self):
        args = self.args()
        path = prepare_run.prepare(args)
        sentinel = path.parent / "results.jsonl"
        sentinel.write_text("existing-record\n", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            prepare_run.prepare(args)
        self.assertEqual("existing-record\n", sentinel.read_text("utf-8"))
        self.assert_template_unchanged()

    def test_changed_official_goal_or_reference_is_rejected(self):
        path = self.repo / "benchmarks/golden_gate/painting_goal.txt"
        original = path.read_bytes()
        path.write_bytes(b"Different official goal\n")
        with self.assertRaisesRegex(ValueError, "official goal"):
            prepare_run.prepare(self.args())
        path.write_bytes(original)
        (self.task / "References/GoldenGateBridge_reference.png").write_bytes(b"not-the-original")
        with self.assertRaisesRegex(ValueError, "locked runtime"):
            prepare_run.prepare(self.args())
        self.assertFalse((self.root / "run").exists())

    def test_goal_uses_utf16_limit_and_refuses_empty_or_control_text(self):
        for data in (b" \n", b"a\x00b", ("\U0001f426" * 4097).encode("utf-8")):
            with self.subTest(data_length=len(data)), self.assertRaises(ValueError):
                prepare_run.validate_goal(data)

    def test_changed_task_binary_is_rejected_before_preparing_a_run(self):
        (self.task / "dll/RobotPainting.dll").write_bytes(b"different task code")
        with self.assertRaisesRegex(ValueError, "locked runtime"):
            prepare_run.prepare(self.args())
        self.assertFalse((self.root / "run").exists())

    def test_prefab_template_is_rejected_without_rewriting_it(self):
        active = self.mods / "config.yaml"
        active.write_text("override_by_task: false\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "prefab mode"):
            prepare_run.prepare(self.args())
        self.assertEqual("override_by_task: false\n", active.read_text("utf-8"))

    def test_custom_reference_obeys_task107_dimensions_and_format(self):
        for size, format_name in (((9000, 100), "PNG"), ((5000, 4000), "PNG"), ((32, 24), "WEBP")):
            with self.subTest(size=size, format=format_name):
                path = self.root / "custom.png"
                with Image.new("RGB", size, "white") as pixels:
                    pixels.save(path, format=format_name)
                with self.assertRaises(ValueError):
                    prepare_run.prepare(self.args(extra=("--reference-image", str(path))))
                self.assertFalse((self.root / "run").exists())

    def test_startup_delegates_and_clears_only_task_path_overrides(self):
        path = prepare_run.prepare(self.args())
        launch_spec = importlib.util.spec_from_file_location("run_eval", ROOT / "scripts/run_eval.py")
        launch = importlib.util.module_from_spec(launch_spec)
        launch_spec.loader.exec_module(launch)
        environment = {name: "stale-template-or-editor-path" for name in launch.TASK_PATH_OVERRIDES}
        environment.update(OPENROUTER_API_KEY="offline-test-key", DISPLAY=":test-display")
        with patch.dict("os.environ", environment), patch("agent_ark.ark_eval.run_api_agent.main") as runner:
            launch.main(["--config", str(path)])
            runner.assert_called_once()
            self.assertEqual(str(path), runner.call_args.args[0].config)
            for name in launch.TASK_PATH_OVERRIDES:
                self.assertEqual("", __import__("os").environ[name])
            self.assertEqual("offline-test-key", __import__("os").environ["OPENROUTER_API_KEY"])
            self.assertEqual(":test-display", __import__("os").environ["DISPLAY"])


class VersionSnapshotTests(unittest.TestCase):
    def test_snapshot_matches_installed_defaults_and_goals(self):
        lock = json.loads((ROOT / "benchmarks/versions.json").read_text("utf-8"))
        self.assertEqual(asdict(SimpleRuntimeConfig()), lock["simple_agent_context_defaults"])
        self.assertEqual(asdict(ToolLimits(max_records=512)), lock["simple_agent_tool_limits_defaults"])
        for case in prepare_run.CASES:
            goal = ROOT / "benchmarks" / case / "painting_goal.txt"
            self.assertEqual(prepare_run.sha256(goal), lock["goals"][case]["sha256"])
            self.assertNotIn(b"\r", goal.read_bytes())


if __name__ == "__main__":
    unittest.main()
