"""Offline tests for the no-inference record notebook and thin adapter."""
import ast
import base64
from copy import deepcopy
import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import re
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from unittest.mock import Mock, patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("colab_record", ROOT / "scripts/colab_record.py")
record = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record)


class ColabRecordTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "public-record.jsonl"
        self.source.write_bytes(b'{"fixture":"no model or Player may run"}\n')
        self.contract = record.record_contract()
        self.contract.update(bytes=self.source.stat().st_size, sha256=record.sha256(self.source))
        for guard in (
            patch.object(record, "record_contract", return_value=self.contract),
            patch.object(socket.socket, "connect", side_effect=AssertionError("No network in offline tests")),
        ):
            guard.start()
            self.addCleanup(guard.stop)

    def seed_prepare(self, args):
        output = Path(args.output_dir)
        output.mkdir()
        cfg = yaml.safe_load((ROOT / f"benchmarks/{args.case}/eval.yaml").read_text("utf-8"))
        cfg["env_cfg"]["additional_args"] = ["-force-glcore33", "-logFile", str(output / "player.log")]
        path = output / "eval.yaml"
        path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        (output / "manifest.json").write_text(json.dumps({"preparation_only": True,
            "protocol": {"max_attempts": 3, "max_steps_per_attempt": 96}}), encoding="utf-8")
        self.seed_args = args
        return path

    def prepare(self, mode="replay", name="run", extra=()):
        args = record.parser().parse_args(["prepare", "--mode", mode, "--run-dir", str(self.root / name),
            "--record-path", str(self.source), "--env-path", "/fixture/player", "--mod-path", "/fixture/mods", *extra])
        with patch.object(record.prepare_run, "prepare", side_effect=self.seed_prepare):
            return record.prepare(args)

    def test_download_verifies_before_copying_and_preserves_existing_destination(self):
        destination = self.root / "downloaded.jsonl"
        downloader = Mock(return_value=str(self.source))
        result = record.download_record(destination, downloader=downloader)
        self.assertTrue(result["verified"])
        self.assertEqual(self.source.read_bytes(), destination.read_bytes())
        self.assertEqual(self.contract["revision"], downloader.call_args.kwargs["revision"])
        with self.assertRaises(FileExistsError):
            record.download_record(destination, downloader=downloader)
        self.assertEqual(1, downloader.call_count)

    def test_wrong_record_bytes_are_rejected_without_output(self):
        self.source.write_bytes(b"tampered")
        destination = self.root / "must-not-exist.jsonl"
        with self.assertRaisesRegex(ValueError, "locked size/SHA"):
            record.download_record(destination, downloader=lambda **_: str(self.source))
        self.assertFalse(destination.exists())

    def test_replay_preparation_reuses_preparer_and_existing_replay_contract(self):
        path = self.prepare(extra=("--render-mode", "existing-display", "--graphics-api", "vulkan", "--task-store", "/fixture/store"))
        cfg = yaml.safe_load(path.read_text("utf-8"))
        self.assertNotIn("models", cfg)
        self.assertNotIn("eval", cfg)
        self.assertTrue(cfg["replay"]["require_match"])
        self.assertTrue(cfg["replay"]["use_record_max_attempts"])
        self.assertFalse(cfg["hooks"]["human_interaction"]["enabled"])
        self.assertEqual("/fixture/store", self.seed_args.task_store)
        self.assertEqual("existing-display", self.seed_args.render_mode)
        arguments = cfg["env_cfg"]["additional_args"]
        self.assertIn("-force-vulkan", arguments)
        self.assertNotIn("-force-glcore33", arguments)
        manifest = json.loads((path.parent / "manifest.json").read_text("utf-8"))
        self.assertEqual(record.sha256(path), manifest["eval_config_sha256"])
        self.assertFalse(manifest["model_inference"])
        self.assertEqual("prepared_only_not_runtime_validated", manifest["validation_status"])

    def test_human_preparation_has_no_model_and_preserves_three_attempt_budget(self):
        path = self.prepare(mode="human")
        cfg = yaml.safe_load(path.read_text("utf-8"))
        self.assertEqual("linux", self.seed_args.runtime_platform)
        self.assertEqual("xvfb-software", self.seed_args.render_mode)
        self.assertEqual([], cfg["models"])
        self.assertTrue(cfg["hooks"]["human_interaction"]["enabled"])
        self.assertIsNone(cfg["hooks"]["human_interaction"]["timeout_s"])
        self.assertEqual((3, 96), tuple(cfg["env_cfg"]["env_config_overrides"][key]
                                      for key in ("max_attempts", "max_steps_per_attempt")))

    def test_windows_replay_prepares_existing_display_with_real_preparer_offline(self):
        # Only the immutable runtime identity is synthetic. Exercise the real
        # preparer and AgentArk's read-only merge/loader without launching any
        # Player, viewer, model, Xvfb, download or subprocess.
        from agent_ark.ark_eval.run_api_agent import load_eval_config

        player = self.root / "player"
        player.mkdir()
        executable = player / "AgentArk.exe"
        executable.write_bytes(b"offline fixture - never execute")
        mods = player / "AgentArk_Data/Resources/Mods"
        mods.mkdir(parents=True)
        task = mods / "all_tasks/RobotPainting"
        (task / "cfg").mkdir(parents=True)
        (task / "dll").mkdir()
        (task / "dll/RobotPainting.dll").write_bytes(b"offline fixture")
        (task / "catalog_1.0.json").write_text("{}\n", encoding="utf-8")
        (task / "scene.bundle").write_bytes(b"offline fixture")
        (task / "cfg/task_config.yaml").write_text(yaml.safe_dump({
            "task_name": "RobotPainting", "max_attempts": 3, "max_steps_per_attempt": 96,
            "task_params": {}, "env_wrapper_cfg": {},
        }), encoding="utf-8")
        # A stale virtual-display policy must not activate Xvfb on Windows.
        (mods / "config.yaml.bak").write_text(yaml.safe_dump({
            "task_name": "OldTask", "engine_para": {"time_scale": 1},
            "virtual_display": True, "virtual_display_force": True,
        }), encoding="utf-8")
        (mods / "config.yaml").write_text("task_name: OldTask\n", encoding="utf-8")
        before = {path: path.read_bytes() for path in player.rglob("*") if path.is_file()}
        run_dir = self.root / "windows replay"
        args = record.parser().parse_args([
            "prepare", "--runtime-platform", "windows", "--case", "pelican", "--model", "astra",
            "--record-path", str(self.source), "--run-dir", str(run_dir),
            "--env-path", str(executable), "--mod-path", str(mods), "--task-store", str(task.parent),
        ])
        with patch.object(record.prepare_run, "agentark_identity", return_value={"matches_version_lock": True}), \
                patch.object(record.prepare_run, "check_task_files", return_value=True) as task_check, \
                patch("subprocess.Popen", side_effect=AssertionError("No processes during preparation")):
            path = record.prepare(args)
        self.assertEqual("windows", task_check.call_args.args[1])
        cfg = load_eval_config(str(path))
        env = cfg["env_cfg"]
        self.assertFalse(env["no_graphics"])
        self.assertTrue(env["runtime_sandbox"]["enabled"])
        self.assertEqual("windows", env["runtime_sandbox"]["runtime_platform"])
        self.assertEqual(run_dir / "runtime", Path(env["runtime_sandbox"]["pool_root"]))
        self.assertFalse(env["env_config_overrides"]["virtual_display"])
        self.assertFalse(env["env_config_overrides"]["virtual_display_force"])
        self.assertNotIn("-force-glcore33", env["additional_args"])
        self.assertNotIn("models", cfg)
        self.assertNotIn("eval", cfg)
        self.assertFalse(cfg["robopaint_record"]["model_inference"])
        self.assertTrue(cfg["hooks"]["visualization"]["enabled"])
        self.assertEqual("127.0.0.1", cfg["hooks"]["visualization"]["host"])
        self.assertFalse(cfg["hooks"]["human_interaction"]["enabled"])
        self.assertEqual(run_dir / "replay_results.jsonl", Path(cfg["replay"]["output_path"]))
        manifest = json.loads((run_dir / "manifest.json").read_text("utf-8"))
        self.assertEqual("windows", manifest["runtime_platform"])
        self.assertEqual("existing-display", manifest["rendering"]["requested_mode"])
        self.assertEqual("prepared_only_not_runtime_validated", manifest["validation_status"])
        self.assertEqual(before, {path: path.read_bytes() for path in player.rglob("*") if path.is_file()})

    def test_windows_replay_refuses_explicit_xvfb_before_creating_output(self):
        args = record.parser().parse_args([
            "prepare", "--runtime-platform", "windows", "--render-mode", "xvfb-software",
            "--record-path", str(self.source), "--run-dir", str(self.root / "must-not-exist"),
        ])
        with self.assertRaisesRegex(ValueError, "Linux-only"):
            record.prepare(args)
        self.assertFalse((self.root / "must-not-exist").exists())

    def test_pelican_preparation_selects_text_case_without_constructing_source_model(self):
        with patch.object(record, "record_contract", return_value=self.contract) as contract:
            path = self.prepare(extra=("--case", "pelican", "--model", "astra"))
        contract.assert_called_once_with("pelican", "astra")
        cfg = yaml.safe_load(path.read_text("utf-8"))
        self.assertEqual("pelican", self.seed_args.case)
        self.assertEqual("text", cfg["env_cfg"]["env_config_overrides"]["task_params"]["reference_mode"])
        self.assertEqual([], cfg["env_cfg"]["env_config_overrides"]["env_wrapper_cfg"]["attempt_initial_images"])
        self.assertNotIn("models", cfg)
        self.assertEqual("astra", cfg["robopaint_record"]["source_model"])
        manifest = json.loads((path.parent / "manifest.json").read_text("utf-8"))
        self.assertEqual("astra", manifest["model"]["source_record_model"])
        self.assertFalse(manifest["model_inference"])

    def test_selected_download_uses_case_and_model_identity_before_copy(self):
        with patch.object(record, "record_contract", return_value=self.contract) as contract:
            record.download_record(self.root / "selected.jsonl", case="pelican", model="mimo",
                                   downloader=lambda **_: str(self.source))
        contract.assert_called_once_with("pelican", "mimo")

    def test_human_launch_delegates_once_and_refuses_overwrite(self):
        path = self.prepare(mode="human")
        with patch.dict(os.environ), patch.object(record.run_eval, "main") as upstream:
            record.launch(path)
            upstream.assert_called_once_with(["--config", str(path)])
            self.assertEqual("", os.environ["AGENTARK_TASK107_VIDEO_DIR"])
            with self.assertRaises(FileExistsError):
                record.launch(path)
            self.assertEqual(1, upstream.call_count)

    def test_edited_human_api_model_is_rejected_before_start(self):
        path = self.prepare(mode="human")
        cfg = yaml.safe_load(path.read_text("utf-8"))
        cfg["models"] = [{"provider": "openrouter", "model": "never-call"}]
        path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        with patch.object(record.run_eval, "main") as upstream:
            with self.assertRaisesRegex(ValueError, "empty models"):
                record.launch(path)
            upstream.assert_not_called()
        self.assertFalse((path.parent / "session_started.json").exists())

    def test_existing_result_is_preserved_even_without_start_marker(self):
        path = self.prepare(mode="human")
        result = path.parent / "results.jsonl"
        result.write_bytes(b"retained-result\n")
        with patch.object(record.run_eval, "main") as upstream:
            with self.assertRaisesRegex(FileExistsError, "artifacts already exist"):
                record.launch(path)
            upstream.assert_not_called()
        self.assertEqual(b"retained-result\n", result.read_bytes())

    def test_inspection_reports_log_and_declares_video_decode_unverified(self):
        out = self.root / "inspection"
        episode = out / "videos/attempt_1_example"
        episode.mkdir(parents=True)
        (out / "player.log").write_text("Renderer: Tesla T4/PCIe/SSE2\nVendor: NVIDIA Corporation\n", encoding="utf-8")
        (episode / "motion.mp4").write_bytes(b"not decoded")
        (episode / "manifest.json").write_text(json.dumps({"complete": True, "truncated": False,
            "encoder_exit_code": 0, "frames": 12}), encoding="utf-8")
        result = record.inspect_run(out)
        self.assertFalse(result["runtime_pass_claimed"])
        self.assertEqual(2, len(result["renderer_log_evidence"]))
        self.assertFalse(result["recording_manifests"][0]["decode_verified"])


class PublicRecordAndNotebookTests(unittest.TestCase):
    def test_actual_public_sol_identity_matches_verified_release(self):
        entry = record.record_contract()
        self.assertEqual(17574365, entry["bytes"])
        self.assertEqual("3189bf011628a6f87c25f910141a5ab0c456ecc7059bb4e52b1364877acdaaaf", entry["sha256"])
        self.assertEqual("1d4f382a163256a9f75e3817b68698c1e73e6fa1", entry["revision"])

    def test_every_public_contract_has_fixed_revision_and_distinct_complete_record(self):
        for case, revision in (("golden_gate", "1d4f382a163256a9f75e3817b68698c1e73e6fa1"),
                               ("pelican", "b16fb52e866ce6a33c52e287f04bfe4a77964453")):
            release = json.loads((ROOT / f"benchmarks/results/{case}.json").read_text("utf-8"))
            filenames = set()
            for model in release["models"]:
                with self.subTest(case=case, model=model["id"]):
                    entry = record.record_contract(case, model["id"])
                    self.assertEqual(revision, entry["revision"])
                    self.assertIn(f"/{case}/", entry["filename"])
                    self.assertTrue(entry["all_actions_complete"])
                    self.assertEqual(model["record"]["sha256"], entry["sha256"])
                    filenames.add(entry["filename"])
            self.assertEqual(11, len(filenames))
        for case, model in (("unknown", "sol"), ("pelican", "not-a-model"), ("../../private", "sol")):
            with self.subTest(case=case, model=model), self.assertRaises(ValueError):
                record.record_contract(case, model)

    def test_pelican_notebook_uses_selected_record_and_preserves_no_inference_guards(self):
        notebook = json.loads((ROOT / "notebooks/Pelican_Record_Colab.ipynb").read_text("utf-8"))
        code = []
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                source = "".join(cell["source"])
                ast.parse(source)
                self.assertEqual([], cell["outputs"])
                self.assertIsNone(cell["execution_count"])
                code.append(source)
        joined = "\n".join(code)
        self.assertIn('"--case", "pelican", "--model", RECORD_MODEL', joined)
        self.assertIn('RECORD_MODEL = "sol"', joined)
        self.assertIn('"astra"]', joined)
        self.assertIn('MODE = "replay"', joined)
        self.assertIn('RENDERER = "gpu"', joined)
        self.assertIn('START_SESSION = True', joined)
        self.assertIn('RECORD_MOTION_VIDEO = False', joined)
        self.assertIn('PREPARED_SELECTION != (RECORD_MODEL, MODE,', joined)
        self.assertIn('explicit cleanup cell', joined)
        self.assertNotIn('OPENROUTER_API_KEY', joined)
        self.assertNotIn('ARK_API_KEY', joined)
        self.assertNotIn('public-sol-', joined)

    def test_pelican_embedded_bundle_matches_both_case_contracts_and_current_helpers(self):
        import package_colab_source
        notebook = json.loads((ROOT / "notebooks/Pelican_Record_Colab.ipynb").read_text("utf-8"))
        source = next("".join(cell["source"]) for cell in notebook["cells"]
                      if "def unpack_source_bundle" in "".join(cell["source"]))
        tree = ast.parse(source)
        names = {"SOURCE_ARCHIVE_SHA256", "SOURCE_FILES", "EMBEDDED_SOURCE_ZIP_B64"}
        values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                  and node.targets[0].id in names}
        self.assertEqual(set(package_colab_source.ALLOWED_FILES), set(values["SOURCE_FILES"]))
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "embedded.zip"
            archive.write_bytes(base64.b64decode(values["EMBEDDED_SOURCE_ZIP_B64"], validate=True))
            _, payloads = package_colab_source.verify_archive(archive, values["SOURCE_ARCHIVE_SHA256"])
            for relative, payload in payloads.items():
                expected = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
                self.assertEqual(expected, payload, relative)

    def test_notebook_has_blank_outputs_valid_code_and_no_inference_default(self):
        notebook = json.loads((ROOT / "notebooks/GoldenGate_Record_Colab.ipynb").read_text("utf-8"))
        code = []
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertEqual([], cell["outputs"])
                self.assertIsNone(cell["execution_count"])
                source = "".join(cell["source"])
                ast.parse(source)
                code.append(source)
        joined = "\n".join(code)
        self.assertIn('MODE = "replay"', joined)
        self.assertIn('RENDERER = "gpu"', joined)
        self.assertEqual("GPU", notebook["metadata"]["accelerator"])
        self.assertIn("START_SESSION = True", joined)
        self.assertIn("RECORD_MOTION_VIDEO = False", joined)
        self.assertIn('SOURCE_MODE = "embedded"', joined)
        self.assertIn("SOURCE_ARCHIVE_SHA256", joined)
        self.assertIn("SEND_ACTION = False", joined)
        self.assertIn("STOP_SESSION = False", joined)
        self.assertIn("google.colab.kernel.proxyPort", joined)
        self.assertNotIn("OPENROUTER_API_KEY", joined)
        self.assertNotIn("ARK_API_KEY", joined)
        self.assertIn('graphics["environment"]', joined)
        self.assertIn("LOCAL_CHECKOUT", joined)

    def test_golden_gate_notebook_routes_each_selected_record_to_download_and_prepare(self):
        notebook = json.loads((ROOT / "notebooks/GoldenGate_Record_Colab.ipynb").read_text("utf-8"))
        source = next("".join(c["source"]) for c in notebook["cells"] if c.get("id") == "goldengate-record-06")
        models = json.loads((ROOT / "benchmarks/results/golden_gate.json").read_text("utf-8"))["models"]
        for model in models:
            with self.subTest(model=model["id"]), tempfile.TemporaryDirectory() as temporary:
                tree = ast.parse(source)
                selection = next(node for node in tree.body if isinstance(node, ast.Assign)
                                 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "RECORD_MODEL")
                selection.value = ast.Constant(model["id"])
                ast.fix_missing_locations(tree)
                calls = []
                def fake_run(command, **kwargs):
                    calls.append(command)
                    if command[2] == "prepare":
                        Path(command[command.index("--run-dir") + 1]).mkdir()
                root = Path(temporary)
                process = Mock()
                process.check_output.return_value = "offline-fixture\n"
                scope = {"SESSION": root, "PYTHON": root / "python", "HELPER": root / "helper",
                         "PLAYER": root / "player", "MODS": root / "mods", "STORE": root / "store",
                         "BENCH": root, "RENDERER": "gpu", "RENDER_MODE": "existing-display",
                         "GRAPHICS_API": "glcore33", "SOURCE_RECEIPT": {}, "run": fake_run,
                         "subprocess": process, "json": json, "uuid": uuid}
                with patch("builtins.print"):
                    exec(compile(tree, "notebook-prepare", "exec"), scope)
                download, prepare = calls
                self.assertEqual("download-record", download[2])
                self.assertEqual("prepare", prepare[2])
                for command in calls:
                    self.assertEqual("golden_gate", command[command.index("--case") + 1])
                    self.assertEqual(model["id"], command[command.index("--model") + 1])
                self.assertEqual(download[download.index("--destination") + 1],
                                 prepare[prepare.index("--record-path") + 1])
                self.assertEqual(model["id"], scope["PREPARED_SELECTION"][0])

    def test_single_file_embedded_source_bootstraps_exact_reviewed_files_and_rejects_tampering(self):
        notebook = json.loads((ROOT / "notebooks/GoldenGate_Record_Colab.ipynb").read_text("utf-8"))
        source = next("".join(cell["source"]) for cell in notebook["cells"]
                      if "def unpack_source_bundle" in "".join(cell["source"]))
        tree = ast.parse(source)
        required = {"SOURCE_MODE", "SOURCE_ARCHIVE", "SOURCE_ARCHIVE_SHA256", "LOCAL_CHECKOUT",
                    "SOURCE_FILES", "EMBEDDED_SOURCE_ZIP_B64"}
        defaults = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in required}
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "unpack_source_bundle")
        branch = next(node for node in tree.body if isinstance(node, ast.If)
                      and isinstance(node.test, ast.Call) and isinstance(node.test.func, ast.Attribute)
                      and isinstance(node.test.func.value, ast.Name) and node.test.func.value.id == "LOCAL_CHECKOUT")
        for tampered in (False, True):
            with self.subTest(tampered=tampered), tempfile.TemporaryDirectory() as temporary:
                scope = dict(defaults, Path=Path, base64=base64, hashlib=hashlib, io=io, json=json,
                             re=re, stat=stat, zipfile=zipfile, SESSION=Path(temporary),
                             SOURCE_RECEIPT={"mode": defaults["SOURCE_MODE"]}, run=Mock())
                if tampered:
                    archive = bytearray(base64.b64decode(scope["EMBEDDED_SOURCE_ZIP_B64"], validate=True))
                    archive[len(archive) // 2] ^= 1
                    scope["EMBEDDED_SOURCE_ZIP_B64"] = base64.b64encode(archive).decode("ascii")
                executable = compile(ast.Module(body=[function, branch], type_ignores=[]), "embedded-source", "exec")
                if tampered:
                    with self.assertRaisesRegex(ValueError, "SHA-256 does not match"):
                        exec(executable, scope)
                    self.assertFalse((Path(temporary) / "benchmark").exists())
                else:
                    exec(executable, scope)
                    self.assertEqual("embedded", scope["SOURCE_RECEIPT"]["mode"])
                    self.assertEqual(14, scope["SOURCE_RECEIPT"]["files"])
                    for relative in defaults["SOURCE_FILES"]:
                        expected = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
                        self.assertEqual(expected, (scope["BENCH"] / relative).read_bytes(), relative)
                scope["run"].assert_not_called()

    def test_notebook_bootstrap_checks_exact_source_closure_before_extraction(self):
        notebook = json.loads((ROOT / "notebooks/GoldenGate_Record_Colab.ipynb").read_text("utf-8"))
        source = next("".join(cell["source"]) for cell in notebook["cells"] if "def unpack_source_bundle" in "".join(cell["source"]))
        tree = ast.parse(source)
        allowed_assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                                  and any(isinstance(name, ast.Name) and name.id == "SOURCE_FILES" for name in node.targets))
        allowed = ast.literal_eval(allowed_assignment.value)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "unpack_source_bundle")
        scope = {"SOURCE_FILES": allowed, "hashlib": hashlib, "io": io, "json": json, "re": re, "stat": stat, "zipfile": zipfile}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "notebook-bootstrap", "exec"), scope)
        for flaw in (None, "archive_hash", "extra", "traversal", "duplicate", "link", "member_hash"):
            with self.subTest(flaw=flaw), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "source.zip"
                payloads = {name: ("fixture:" + name).encode() for name in allowed}
                manifest = {"schema": "robopaint.colab-source.v1", "files": [
                    {"path": name, "bytes": len(payloads[name]), "sha256": hashlib.sha256(payloads[name]).hexdigest()}
                    for name in sorted(payloads)]}
                if flaw == "member_hash":
                    payloads[allowed[0]] = b"changed"
                if flaw == "extra":
                    payloads[".env"] = b"must never extract"
                if flaw == "traversal":
                    payloads["../escaped.txt"] = b"must never extract"
                payloads["SOURCE_MANIFEST.json"] = json.dumps(manifest).encode()
                with zipfile.ZipFile(archive, "w") as bundle:
                    for name, content in payloads.items():
                        info = zipfile.ZipInfo(name)
                        info.external_attr = 0o100644 << 16
                        if flaw == "link" and name == allowed[0]:
                            info.external_attr = 0o120777 << 16
                        bundle.writestr(info, content)
                    if flaw == "duplicate":
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", UserWarning)
                            duplicate = zipfile.ZipInfo(allowed[0])
                            duplicate.external_attr = 0o100644 << 16
                            bundle.writestr(duplicate, b"duplicate")
                expected = hashlib.sha256(archive.read_bytes()).hexdigest()
                if flaw == "archive_hash":
                    expected = "0" * 64
                destination = root / "checkout"
                if flaw is None:
                    result = scope["unpack_source_bundle"](archive, destination, expected)
                    self.assertEqual(len(allowed), result["files"])
                    self.assertEqual(payloads[allowed[0]], (destination / allowed[0]).read_bytes())
                else:
                    with self.assertRaises(ValueError):
                        scope["unpack_source_bundle"](archive, destination, expected)
                    self.assertFalse(destination.exists())
                self.assertFalse((root / "escaped.txt").exists())
        # Exercise the actual producer against the independently embedded
        # notebook bootstrap, rather than relying only on synthetic ZIPs.
        import package_colab_source
        self.assertEqual(set(allowed), set(package_colab_source.ALLOWED_FILES))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "curated-source.zip"
            receipt = package_colab_source.pack(ROOT, archive)
            restored = scope["unpack_source_bundle"](archive, root / "restored", receipt["archive_sha256"])
            self.assertEqual(14, restored["files"])
            self.assertEqual((ROOT / "scripts/colab_record.py").read_bytes().replace(b"\r\n", b"\n"),
                             (root / "restored/scripts/colab_record.py").read_bytes())

    def test_gpu_notebook_launch_consumes_all_graphics_unset_variables(self):
        notebook = json.loads((ROOT / "notebooks/GoldenGate_Record_Colab.ipynb").read_text("utf-8"))
        source = next("".join(cell["source"]) for cell in notebook["cells"] if cell.get("id") == "goldengate-record-07")
        tree = ast.parse(source)
        next(node for node in tree.body if isinstance(node, ast.Assign)).value = ast.Constant(True)
        ast.fix_missing_locations(tree)
        unset = ["LIBGL_ALWAYS_SOFTWARE", "GALLIUM_DRIVER", "GALLIUM_NUM_THREADS", "LP_NUM_THREADS",
                 "MESA_LOADER_DRIVER_OVERRIDE", "LIBGL_DRIVERS_PATH"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selection = ("sol", "replay", "gpu", "existing-display", "glcore33", 18181, 5005)
            process = Mock()
            scope = {"RUN": root, "PREPARED_SELECTION": selection, "RECORD_MODEL": "sol", "MODE": "replay", "RENDERER": "gpu",
                     "RENDER_MODE": "existing-display", "GRAPHICS_API": "glcore33", "VIEWER_PORT": 18181,
                     "BASE_PORT": 5005, "GRAPHICS_UNSET_ENV": unset, "GRAPHICS_ENV": {"DISPLAY": ":99"},
                     "RECORD_MOTION_VIDEO": False, "PYTHON": Path("/python"), "HELPER": Path("/helper"),
                     "CONFIG": root / "eval.yaml", "BENCH": root, "subprocess": process, "os": os}
            with patch.dict(os.environ, {key: "inherited-conflict" for key in unset}), patch("builtins.print"):
                exec(compile(tree, "notebook-launch", "exec"), scope)
                environment = process.Popen.call_args.kwargs["env"]
                for key in unset:
                    self.assertNotIn(key, environment)
                    self.assertEqual("inherited-conflict", os.environ[key])
                self.assertEqual(":99", environment["DISPLAY"])
                scope["RECORD_MODEL"] = "argon"
                with self.assertRaisesRegex(RuntimeError, "Selections changed after preparation"):
                    exec(compile(tree, "notebook-launch", "exec"), scope)
                process.Popen.assert_called_once()

    def test_live_session_blocks_prepare_and_launch_without_losing_handle(self):
        notebook = json.loads((ROOT / "notebooks/GoldenGate_Record_Colab.ipynb").read_text("utf-8"))
        for title in ("# @title 5.", "# @title 6."):
            with self.subTest(cell=title):
                source = next("".join(cell["source"]) for cell in notebook["cells"] if title in "".join(cell["source"]))
                tree = ast.parse(source)
                if title == "# @title 6.":
                    next(node for node in tree.body if isinstance(node, ast.Assign)).value = ast.Constant(True)
                    ast.fix_missing_locations(tree)
                owned = Mock()
                owned.poll.return_value = None
                previous_run = Path("previous-retained-run")
                scope = {"session_process": owned, "RUN": previous_run, "MODE": "human", "run": Mock(), "subprocess": Mock()}
                with self.assertRaisesRegex(RuntimeError, "explicit cleanup cell"):
                    exec(compile(tree, "notebook-session-guard", "exec"), scope)
                self.assertIs(owned, scope["session_process"])
                self.assertEqual(previous_run, scope["RUN"])
                self.assertEqual("human", scope["MODE"])
                scope["run"].assert_not_called()
                scope["subprocess"].Popen.assert_not_called()

    def test_cleanup_signals_only_owned_group_and_has_bounded_escalation(self):
        notebook = json.loads((ROOT / "notebooks/GoldenGate_Record_Colab.ipynb").read_text("utf-8"))
        source = next("".join(cell["source"]) for cell in notebook["cells"] if "def stop_owned_session" in "".join(cell["source"]))
        function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef))
        scope = {"os": os, "signal": signal, "subprocess": subprocess}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "notebook-owned-cleanup", "exec"), scope)
        for scenario in ("normal", "timeout", "wrong_group", "wrong_receipt", "already_exited"):
            with self.subTest(scenario=scenario):
                owned = Mock(pid=4321)
                owned.poll.return_value = 0 if scenario == "already_exited" else None
                if scenario == "timeout":
                    owned.wait.side_effect = [subprocess.TimeoutExpired("owned-fixture", 15), 0]
                with patch.object(os, "getpgid", return_value=9876 if scenario == "wrong_group" else 4321, create=True) as group, \
                        patch.object(os, "killpg", create=True) as send, \
                        patch.object(signal, "SIGKILL", 9, create=True):
                    if scenario in ("wrong_group", "wrong_receipt"):
                        with self.assertRaisesRegex(RuntimeError, "no signal was sent"):
                            scope["stop_owned_session"](owned, 9876 if scenario == "wrong_receipt" else 4321)
                        send.assert_not_called()
                    else:
                        scope["stop_owned_session"](owned, 4321)
                        if scenario == "already_exited":
                            send.assert_not_called()
                            group.assert_not_called()
                        elif scenario == "timeout":
                            self.assertEqual([(4321, signal.SIGTERM), (4321, signal.SIGKILL)],
                                             [call.args for call in send.call_args_list])
                            self.assertEqual([15, 5], [call.kwargs["timeout"] for call in owned.wait.call_args_list])
                        else:
                            send.assert_called_once_with(4321, signal.SIGTERM)
                            owned.wait.assert_called_once_with(timeout=15)

    def test_signal_bootstrap_uses_upstream_finally_cleanup_and_apt_is_noninteractive(self):
        notebook = json.loads((ROOT / "notebooks/GoldenGate_Record_Colab.ipynb").read_text("utf-8"))
        launch = next("".join(cell["source"]) for cell in notebook["cells"] if "SIGNAL_BOOTSTRAP =" in "".join(cell["source"]))
        assignment = next(node for node in ast.walk(ast.parse(launch)) if isinstance(node, ast.Assign)
                          and any(isinstance(name, ast.Name) and name.id == "SIGNAL_BOOTSTRAP" for name in node.targets))
        bootstrap = ast.parse(ast.literal_eval(assignment.value))
        handler = next(node for node in bootstrap.body if isinstance(node, ast.FunctionDef))
        self.assertTrue(any(isinstance(node, ast.Raise) for node in ast.walk(handler)))
        self.assertIn("KeyboardInterrupt", ast.literal_eval(assignment.value))
        self.assertIn("signal.SIGTERM", ast.literal_eval(assignment.value))
        first = next("".join(cell["source"]) for cell in notebook["cells"] if "def unpack_source_bundle" in "".join(cell["source"]))
        runner = next(node for node in ast.parse(first).body if isinstance(node, ast.FunctionDef) and node.name == "run")
        child = Mock()
        scope = {"Path": Path, "os": os, "subprocess": child}
        exec(compile(ast.Module(body=[runner], type_ignores=[]), "notebook-install-runner", "exec"), scope)
        previous = os.environ.get("DEBIAN_FRONTEND")
        with patch("builtins.print") as progress:
            scope["run"](["apt-get", "install", "xserver-xorg-core"])
            self.assertEqual("noninteractive", child.run.call_args.kwargs["env"]["DEBIAN_FRONTEND"])
            self.assertTrue(progress.call_args.kwargs["flush"])
        self.assertEqual(previous, os.environ.get("DEBIAN_FRONTEND"))

    def test_rerender_reuses_owned_verified_xorg_and_preserves_receipt(self):
        notebook = json.loads((ROOT / "notebooks/GoldenGate_Record_Colab.ipynb").read_text("utf-8"))
        source = next("".join(cell["source"]) for cell in notebook["cells"] if "# @title 4." in "".join(cell["source"]))
        for mismatch in (False, True):
            with self.subTest(identity_changed=mismatch), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                receipt = {"xorg_pid": 4321, "display": ":99", "environment": {"DISPLAY": ":99"},
                           "unset_environment": ["MESA_LOADER_DRIVER_OVERRIDE"]}
                path = directory / "graphics.json"
                original = json.dumps(receipt).encode()
                path.write_bytes(original)
                config = "changed-config" if mismatch else str(directory / "xorg.conf")
                argv = ("/usr/lib/xorg/Xorg\0:99\0-config\0" + config + "\0").encode()
                child = Mock()
                child.run.return_value.stdout = "OpenGL vendor string: NVIDIA Corporation\nOpenGL renderer string: Tesla T4\n"
                scope = {"GRAPHICS_DIR": directory, "Path": Path, "json": json, "os": os,
                         "subprocess": child, "run": Mock()}
                with patch.object(Path, "read_bytes", return_value=argv), patch("builtins.print"):
                    if mismatch:
                        with self.assertRaisesRegex(RuntimeError, "identity changed"):
                            exec(compile(source, "notebook-reuse-display", "exec"), scope)
                        child.run.assert_not_called()
                    else:
                        exec(compile(source, "notebook-reuse-display", "exec"), scope)
                        child.run.assert_called_once()
                scope["run"].assert_not_called()
                self.assertEqual(directory, scope["GRAPHICS_DIR"])
                self.assertEqual(original, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
