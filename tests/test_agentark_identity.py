"""Offline source/provenance identity checks; no installation or runtime launch."""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import agent_ark
from agent_ark.agent.simple_agent.runtime import SimpleRuntimeConfig
from agent_ark.agent.simple_agent.tools import ToolLimits


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("identity_prepare_run", ROOT / "scripts/prepare_run.py")
prepare_run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_run)


class AgentArkIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="robopaint-identity-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.checkout = self.root / "checkout"
        (self.checkout / ".git").mkdir(parents=True)
        self.commit = "a" * 40
        self.lock = {
            "agentark": {"commit": self.commit},
            "simple_agent_context_defaults": asdict(SimpleRuntimeConfig()),
            "simple_agent_tool_limits_defaults": asdict(ToolLimits(max_records=512)),
        }
        network = patch.object(socket.socket, "connect", side_effect=AssertionError("No network"))
        network.start()
        self.addCleanup(network.stop)

    def package(self, relative):
        package = self.checkout / relative / "agent_ark"
        package.mkdir(parents=True)
        entry = package / "__init__.py"
        entry.write_text("# inert identity fixture\n", encoding="utf-8")
        return entry

    def test_noneditable_vcs_install_in_unrelated_checkout_uses_distribution_commit(self):
        entry = self.package(".venv/Lib/site-packages")
        provenance = {"url": "https://github.com/P90-RushB/AgentArk.git",
                      "vcs_info": {"vcs": "git", "commit_id": self.commit}}
        distribution = Mock()
        distribution.read_text.return_value = json.dumps(provenance)

        def untracked(command, **kwargs):
            self.assertEqual("ls-files", command[3])
            self.assertEqual(subprocess.DEVNULL, kwargs["stderr"])
            raise subprocess.CalledProcessError(1, command)

        with patch.object(agent_ark, "__file__", str(entry)), \
                patch.object(prepare_run.subprocess, "check_output", side_effect=untracked) as git, \
                patch.object(prepare_run.metadata, "distribution", return_value=distribution):
            identity = prepare_run.agentark_identity(self.lock, False)
        self.assertEqual(self.commit, identity["commit"])
        self.assertIsNone(identity["source_dirty"])
        self.assertTrue(identity["matches_version_lock"])
        git.assert_called_once()
        distribution.read_text.assert_called_once_with("direct_url.json")

    def test_tracked_source_uses_live_commit_and_rejects_dirty_editable(self):
        entry = self.package("AgentArk")
        for dirty in (False, True):
            with self.subTest(dirty=dirty):
                provenance = {"dir_info": {"editable": True},
                              "vcs_info": {"commit_id": self.commit}}
                distribution = Mock()
                distribution.read_text.return_value = json.dumps(provenance)
                git_output = ["AgentArk/agent_ark/__init__.py\n", self.commit + "\n",
                              " M AgentArk/agent_ark/ark_env.py\n" if dirty else ""]
                with patch.object(agent_ark, "__file__", str(entry)), \
                        patch.object(prepare_run.subprocess, "check_output", side_effect=git_output) as git, \
                        patch.object(prepare_run.metadata, "distribution", return_value=distribution) as metadata:
                    if dirty:
                        with self.assertRaisesRegex(ValueError, "source_dirty=True"):
                            prepare_run.agentark_identity(self.lock, False)
                    else:
                        identity = prepare_run.agentark_identity(self.lock, False)
                        self.assertEqual(self.commit, identity["commit"])
                        self.assertFalse(identity["source_dirty"])
                        self.assertTrue(identity["matches_version_lock"])
                    metadata.assert_not_called()
                self.assertEqual(["ls-files", "rev-parse", "status"],
                                 [call.args[0][3] for call in git.call_args_list])

    def test_tracked_source_commit_mismatch_is_not_hidden_by_installed_provenance(self):
        entry = self.package("AgentArk")
        wrong_commit = "b" * 40
        distribution = Mock()
        distribution.read_text.return_value = json.dumps({"vcs_info": {"commit_id": self.commit}})
        with patch.object(agent_ark, "__file__", str(entry)), \
                patch.object(prepare_run.subprocess, "check_output",
                             side_effect=["AgentArk/agent_ark/__init__.py\n", wrong_commit + "\n", ""]), \
                patch.object(prepare_run.metadata, "distribution", return_value=distribution) as metadata:
            with self.assertRaisesRegex(ValueError, "commit=" + wrong_commit):
                prepare_run.agentark_identity(self.lock, False)
            metadata.assert_not_called()

    def test_untracked_editable_cannot_claim_a_stale_vcs_provenance_commit(self):
        entry = self.package("editable-source")
        distribution = Mock()
        distribution.read_text.return_value = json.dumps({
            "dir_info": {"editable": True}, "vcs_info": {"commit_id": self.commit},
        })
        with patch.object(agent_ark, "__file__", str(entry)), \
                patch.object(prepare_run.subprocess, "check_output",
                             side_effect=subprocess.CalledProcessError(1, "git ls-files")), \
                patch.object(prepare_run.metadata, "distribution", return_value=distribution):
            with self.assertRaisesRegex(ValueError, "commit=None"):
                prepare_run.agentark_identity(self.lock, False)
            identity = prepare_run.agentark_identity(deepcopy(self.lock), True)
        self.assertFalse(identity["matches_version_lock"])
        self.assertIsNone(identity["commit"])

    def test_git_identity_failure_does_not_silently_fall_back_to_provenance(self):
        entry = self.package("AgentArk")
        with patch.object(agent_ark, "__file__", str(entry)), \
                patch.object(prepare_run.subprocess, "check_output",
                             side_effect=subprocess.CalledProcessError(128, "git ls-files")), \
                patch.object(prepare_run.metadata, "distribution") as metadata:
            with self.assertRaises(subprocess.CalledProcessError):
                prepare_run.agentark_identity(self.lock, False)
            metadata.assert_not_called()


if __name__ == "__main__":
    unittest.main()
