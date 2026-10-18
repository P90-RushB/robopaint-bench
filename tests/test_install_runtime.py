"""Installer checks use tiny ZIP fixtures; no network, Unity or model is used."""
import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import socket
import shutil
import stat
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install_runtime", ROOT / "scripts/install_runtime.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class RuntimeInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="robopaint-installer-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "checkout"
        (self.repo / "benchmarks").mkdir(parents=True)
        self.lock = {"runtime_downloads": {
            "repo_id": "P90-RushB/AgentArk", "repo_type": "dataset", "revision": "1" * 40,
            "envs": {}, "tasks": {}}}
        self.archives = {}
        for platform, executable in installer.EXECUTABLES.items():
            env = self.zip(f"env-{platform}.zip", {
                f"release/Player/{executable}": b"Player fixture; never execute",
                "release/Player/UnityCrashHandler64": b"crash-handler fixture",
                "release/Player/AgentArk_Data/Resources/Mods/config.yaml.bak": b"immutable baseline\n",
                "release/Player/AgentArk_Data/Resources/Mods/config.yaml": b"task_name: RobotPainting\n"})
            task = self.zip(f"task-{platform}.zip", self.task_files())
            for kind, path in (("envs", env), ("tasks", task)):
                self.archives[path.name] = path
                self.lock["runtime_downloads"][kind][platform] = self.entry(path)
        self.write_lock()
        self.downloader = Mock(side_effect=lambda **kwargs: self.archives[kwargs["filename"]])
        for guard in (patch.object(installer, "ROOT", self.repo),
                      patch("subprocess.Popen", side_effect=AssertionError("Must not launch a process")),
                      patch.object(socket.socket, "connect", side_effect=AssertionError("Must not use the network"))):
            guard.start()
            self.addCleanup(guard.stop)

    def task_files(self, prefix=""):
        return {prefix + name: payload for name, payload in {
            "cfg/task_config.yaml": b"task_name: RobotPainting\n",
            "dll/RobotPainting.dll": b"DLL fixture",
            "catalog_1.0.json": b"{}\n", "scene.bundle": b"Addressables fixture",
            "References/GoldenGateBridge_reference.png": b"image fixture",
            "LICENSE.txt": b"fixture attribution\n"}.items()}

    def zip(self, name, files):
        path = self.root / name
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in files.items():
                archive.writestr(name, payload)
        return path

    def entry(self, path):
        return {"path": path.name, "bytes": path.stat().st_size, "sha256": installer.sha256(path)}

    def write_lock(self):
        (self.repo / "benchmarks/versions.json").write_text(json.dumps(self.lock), encoding="utf-8")

    def args(self, platform="linux", destination="new install"):
        return argparse.Namespace(platform=platform, destination=str(self.root / destination), cache_dir=None)

    def replace_task(self, path):
        self.archives[path.name] = path
        self.lock["runtime_downloads"]["tasks"]["linux"] = self.entry(path)
        self.write_lock()

    def test_both_platforms_install_only_locked_artifacts_with_hf_cache_auth_defaults(self):
        for platform, executable in installer.EXECUTABLES.items():
            with self.subTest(platform=platform):
                args = self.args(platform, platform)
                args.cache_dir = str(self.root / "HF cache")
                paths = installer.install(args, downloader=self.downloader)
                self.assertEqual(Path(args.destination) / executable, paths["AGENTARK_ENV_PATH"])
                mods = paths["AGENTARK_MOD_PATH"]
                self.assertEqual(b"immutable baseline\n", (mods / "config.yaml.bak").read_bytes())
                task = paths["AGENTARK_TASK_STORE_PATH"] / "RobotPainting"
                for name, payload in self.task_files().items():
                    self.assertEqual(payload, (task / name).read_bytes())
                calls = self.downloader.call_args_list[-2:]
                self.assertEqual([f"env-{platform}.zip", f"task-{platform}.zip"],
                                 [call.kwargs["filename"] for call in calls])
                expected_cache = installer.windows_long_path(args.cache_dir) if os.name == "nt" else args.cache_dir
                for call in calls:
                    self.assertEqual({"repo_id": "P90-RushB/AgentArk", "repo_type": "dataset",
                                      "revision": "1" * 40, "cache_dir": expected_cache},
                                     {key: value for key, value in call.kwargs.items() if key != "filename"})
                if platform == "linux" and os.name != "nt":
                    self.assertTrue(paths["AGENTARK_ENV_PATH"].stat().st_mode & stat.S_IXUSR)
                self.assertEqual([], list(self.root.glob(f".{platform}.install-*")))

    def test_windows_cache_paths_handle_drive_unc_and_existing_extended_prefixes(self):
        for source, expected in (
                ("C:/HF cache/one/../hub", r"\\?\C:\HF cache\hub"),
                (r"\\server\share\HF cache\one\..\hub", r"\\?\UNC\server\share\HF cache\hub"),
                (r"\\?\C:\cache\hub", r"\\?\C:\cache\hub"),
                (r"\\?\UNC\server\share\hub", r"\\?\UNC\server\share\hub")):
            with self.subTest(source=source):
                self.assertEqual(expected, installer.windows_long_path(source))

    def test_default_cache_comes_from_hf_constants_without_changing_auth_options(self):
        # Exercise the real-import branch without requiring the optional HF
        # dependency in the offline test environment or allowing network access.
        hf = ModuleType("huggingface_hub")
        hf.constants = SimpleNamespace(HF_HUB_CACHE=str(self.root / "configured HF home" / "hub"))
        hf.hf_hub_download = self.downloader
        with patch.dict(sys.modules, {"huggingface_hub": hf}):
            installer.install(self.args(), downloader=None)
        expected_cache = installer.windows_long_path(hf.constants.HF_HUB_CACHE) if os.name == "nt" else None
        for call in self.downloader.call_args_list:
            self.assertEqual(expected_cache, call.kwargs["cache_dir"])
            self.assertNotIn("token", call.kwargs)
            self.assertNotIn("force_download", call.kwargs)

    @unittest.skipUnless(os.name == "nt", "Windows extended-path filesystem behavior")
    def test_deep_windows_installation_and_staging_preserve_files_and_readable_paths(self):
        deep_base = self.root / "deep installation test"
        # The test's explicit extended root also keeps its temporary cleanup safe.
        self.addCleanup(lambda: shutil.rmtree(installer.filesystem_path(deep_base), ignore_errors=True))
        parent = deep_base
        for index in range(5):
            parent /= f"component-{index}-" + "x" * 40
        args = self.args("windows")
        args.destination = str(parent / "new player")
        self.assertGreater(len(args.destination), 260)
        paths = installer.install(args, downloader=self.downloader)
        self.assertEqual(Path(args.destination) / "AgentArk.exe", paths["AGENTARK_ENV_PATH"])
        self.assertFalse(str(paths["AGENTARK_ENV_PATH"]).startswith("\\\\?\\"))
        self.assertTrue(installer.filesystem_path(paths["AGENTARK_ENV_PATH"]).is_file())
        baseline = installer.filesystem_path(paths["AGENTARK_MOD_PATH"] / "config.yaml.bak")
        self.assertEqual(b"immutable baseline\n", baseline.read_bytes())
        task = installer.filesystem_path(paths["AGENTARK_TASK_STORE_PATH"] / "RobotPainting")
        for name, payload in self.task_files().items():
            self.assertEqual(payload, (task / name).read_bytes())
        self.assertEqual([], list(installer.filesystem_path(parent).glob(".new player.install-*")))
        self.downloader.reset_mock()
        with self.assertRaises(FileExistsError):
            installer.install(args, downloader=self.downloader)
        self.downloader.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows extended-path filesystem behavior")
    def test_windows_display_paths_round_trip_drive_and_unc(self):
        for value in (r"C:\cache\hub", r"\\server\share\hub"):
            with self.subTest(value=value):
                self.assertEqual(Path(value), installer.display_path(installer.filesystem_path(value)))

    def test_single_task_wrapper_is_supported(self):
        self.replace_task(self.zip("wrapped.zip", self.task_files("RobotPainting/")))
        paths = installer.install(self.args(), downloader=self.downloader)
        self.assertTrue((paths["AGENTARK_TASK_STORE_PATH"] / "RobotPainting/cfg/task_config.yaml").is_file())

    def test_existing_destination_is_refused_before_download_without_touching_records(self):
        args = self.args()
        destination = Path(args.destination)
        destination.mkdir()
        sentinel = destination / "records.json"
        sentinel.write_bytes(b"existing results must remain")
        with self.assertRaises(FileExistsError):
            installer.install(args, downloader=self.downloader)
        self.downloader.assert_not_called()
        self.assertEqual(b"existing results must remain", sentinel.read_bytes())

    def test_existing_destination_created_during_download_is_also_refused(self):
        args = self.args()
        original = self.downloader.side_effect

        def concurrent_destination(**kwargs):
            path = original(**kwargs)
            if kwargs["filename"].startswith("task-"):
                Path(args.destination).mkdir()
                (Path(args.destination) / "records.json").write_text("retained", encoding="utf-8")
            return path

        self.downloader.side_effect = concurrent_destination
        with self.assertRaises(FileExistsError):
            installer.install(args, downloader=self.downloader)
        self.assertEqual("retained", (Path(args.destination) / "records.json").read_text("utf-8"))

    def test_wrong_size_or_hash_never_creates_an_installation(self):
        for field, value in (("bytes", 1), ("sha256", "0" * 64)):
            with self.subTest(field=field):
                original = deepcopy(self.lock)
                self.lock["runtime_downloads"]["tasks"]["linux"][field] = value
                self.write_lock()
                with self.assertRaisesRegex(ValueError, "bytes/SHA-256"):
                    installer.install(self.args(), downloader=self.downloader)
                self.assertFalse(Path(self.args().destination).exists())
                self.lock = original

    def test_unlocked_or_unsafe_download_contract_is_refused(self):
        downloads = self.lock["runtime_downloads"]
        for key, value in (("revision", "main"), ("repo_type", "model")):
            changed = deepcopy(self.lock)
            changed["runtime_downloads"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                installer.download_contract(changed, "linux")
        downloads["tasks"]["linux"]["path"] = "../outside.zip"
        with self.assertRaises(ValueError):
            installer.download_contract(self.lock, "linux")

    def test_unsafe_zip_members_are_rejected_before_any_extraction(self):
        for index, name in enumerate(("../outside.txt", "/absolute.txt", "C:/drive.txt", "safe/../../outside.txt",
                                     "safe\\outside.txt", "safe/./file", "safe//file", "safe/CON.txt", "safe/file:stream")):
            with self.subTest(name=name):
                archive = self.zip("malicious.zip", {"safe.txt": b"safe", name: b"unsafe"})
                if "\\" in name:
                    # ZipInfo normalizes Windows separators while writing; model
                    # an externally supplied ZIP's original header bytes.
                    archive.write_bytes(archive.read_bytes().replace(name.replace("\\", "/").encode(), name.encode()))
                destination = self.root / f"unpacked-{index}"
                with self.assertRaises(ValueError):
                    installer.extract_zip(archive, destination)
                self.assertFalse(destination.exists())
        self.assertFalse((self.root / "outside.txt").exists())

    def test_symlinks_special_files_duplicates_and_file_directory_conflicts_are_rejected(self):
        for kind in ("symlink", "fifo", "duplicate", "case-collision", "file-directory"):
            with self.subTest(kind=kind):
                path = self.root / "bad.zip"
                with warnings.catch_warnings(), zipfile.ZipFile(path, "w") as archive:
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr("safe.txt", b"safe")
                    if kind in ("symlink", "fifo"):
                        info = zipfile.ZipInfo("link")
                        info.create_system = 3
                        info.external_attr = ((stat.S_IFLNK if kind == "symlink" else stat.S_IFIFO) | 0o777) << 16
                        archive.writestr(info, b"../outside")
                    elif kind in ("duplicate", "case-collision"):
                        archive.writestr("safe.txt" if kind == "duplicate" else "SAFE.txt", b"changed")
                    else:
                        archive.writestr("safe.txt/child", b"child")
                destination = self.root / "unpacked"
                with self.assertRaises(ValueError):
                    installer.extract_zip(path, destination)
                self.assertFalse(destination.exists())

    def test_invalid_runtime_structure_leaves_no_destination_or_staging(self):
        files = self.task_files()
        files.pop("dll/RobotPainting.dll")
        self.replace_task(self.zip("incomplete.zip", files))
        with self.assertRaisesRegex(ValueError, "DLL"):
            installer.install(self.args(), downloader=self.downloader)
        self.assertFalse(Path(self.args().destination).exists())
        self.assertEqual([], list(self.root.glob(".new install.install-*")))

    def test_cli_requires_an_explicit_platform_and_new_destination(self):
        args = installer.parser().parse_args(["--platform", "windows", "--destination", "my player"])
        self.assertEqual(("windows", "my player"), (args.platform, args.destination))


if __name__ == "__main__":
    unittest.main()
