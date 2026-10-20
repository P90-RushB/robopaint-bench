"""Offline formal-submission selection tests for the Colab inspection cell."""
import ast
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/GoldenGate_Record_Colab.ipynb"


def inspection_cell():
    notebook = json.loads(NOTEBOOK.read_text("utf-8"))
    return "".join(next(cell for cell in notebook["cells"]
                        if cell.get("id") == "goldengate-record-10")["source"])


def submitted_selector():
    definition = next(node for node in ast.parse(inspection_cell()).body
                      if isinstance(node, ast.FunctionDef) and node.name == "submitted_paintings")
    scope = {}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), "submission-selector", "exec"), scope)
    return scope["submitted_paintings"]


class SubmittedPaintingTests(unittest.TestCase):
    def setUp(self):
        self.select = submitted_selector()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        buffer = io.BytesIO()
        PILImage.new("RGB", (2, 2), "white").save(buffer, format="PNG")
        self.white_png = buffer.getvalue()

    def painting(self, directory, *, guid="guid", saved="2026-10-20T05:01:02.1234567Z", status="submitted",
                 explicit=True, count=5, integrity=True, canvas=True):
        path = self.root / directory
        path.mkdir(parents=True)
        metadata = {"episode_guid": guid, "saved_utc": saved, "terminal_status": status,
                    "explicit_submission": explicit, "action_count": count, "submission_integrity": integrity,
                    "local_episode_counter": 9000}
        (path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        if canvas:
            (path / "canvas.png").write_bytes(self.white_png)
        return path

    def test_formal_white_submission_allowed_startup_reset_disabled_and_staging_excluded(self):
        self.painting("startup", status="startup", explicit=False, count=0)
        self.painting("reset", status="reset", explicit=False, count=0)
        self.painting("disabled", status="disabled", explicit=False, count=0)
        self.painting("false-submit", explicit=False)
        self.painting(".staging_partial/attempt", guid="staging")
        formal = self.painting("formal-white", count=0, integrity=False)
        selected = self.select(self.root)
        self.assertEqual(1, selected["unique_submitted"])
        self.assertEqual(str(formal / "canvas.png"), selected["paintings"][0]["canvas_path"])
        self.assertEqual(0, selected["paintings"][0]["action_count"])
        self.assertIs(False, selected["paintings"][0]["submission_integrity"])
        self.assertEqual({"metadata": 6, "staging": 1, "not_submitted": 4, "duplicates": 0, "incomplete": 0},
                         selected["counts"])

    def test_guid_dedup_and_last_three_sort_by_all_seven_utc_fraction_digits_not_directory_order(self):
        self.painting("zzz_oldest", guid="oldest", saved="2026-10-20T05:01:02.1234560Z")
        self.painting("zzz_duplicate_old", guid="DUP", saved="2026-10-20T05:01:02.1234561Z")
        self.painting("aaa_third", guid="third", saved="2026-10-20T05:01:02.1234562Z")
        duplicate_latest = self.painting("aaa_duplicate_latest", guid="dup", saved="2026-10-20T05:01:02.1234568Z")
        self.painting("000_latest", guid="latest", saved="2026-10-20T05:01:02.1234569Z")
        selected = self.select(self.root)
        self.assertEqual(4, selected["unique_submitted"])
        self.assertEqual(1, selected["counts"]["duplicates"])
        self.assertEqual(["third", "dup", "latest"], [row["episode_guid"] for row in selected["paintings"]])
        self.assertEqual(str(duplicate_latest / "canvas.png"), selected["paintings"][1]["canvas_path"])
        self.assertNotIn("local_episode_counter", selected["paintings"][0])

    def test_incomplete_json_missing_canvas_and_wrong_timestamp_are_reported_without_false_submission(self):
        self.painting("missing-canvas", guid="missing", canvas=False)
        self.painting("short-time", guid="short", saved="2026-10-20T05:01:02.123456Z")
        incomplete = self.root / "partial-json"
        incomplete.mkdir()
        (incomplete / "metadata.json").write_text('{"terminal_status":', encoding="utf-8")
        selected = self.select(self.root)
        self.assertEqual([], selected["paintings"])
        self.assertEqual(0, selected["unique_submitted"])
        self.assertEqual(3, selected["counts"]["incomplete"])
        self.assertEqual(3, len(selected["warnings"]))
        self.assertEqual([], self.select(self.root / "not-yet-created")["paintings"])


class InspectionCellDisplayTests(unittest.TestCase):
    def test_startup_white_is_not_displayed_and_points_to_native_viewer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = io.BytesIO()
            PILImage.new("RGB", (2, 2), "white").save(output, format="PNG")
            startup = root / "paintings/startup"
            startup.mkdir(parents=True)
            (startup / "canvas.png").write_bytes(output.getvalue())
            (startup / "metadata.json").write_text(json.dumps({"terminal_status": "reset", "explicit_submission": False,
                "action_count": 0}), encoding="utf-8")
            display_module = types.ModuleType("IPython.display")
            display_module.HTML = Mock(side_effect=lambda value: ("html", value))
            display_module.Image = Mock(side_effect=lambda **kwargs: ("image", kwargs))
            display_module.display = Mock()
            inspection = types.SimpleNamespace(stdout=json.dumps({"renderer_log_evidence": [
                "Renderer: Tesla T4/PCIe/SSE2", "Vendor: NVIDIA Corporation"]}), stderr="")
            scope = {"PYTHON": Path("python"), "HELPER": Path("helper.py"), "RUN": root,
                     "subprocess": subprocess, "json": json, "re": re, "sys": sys}
            printed = io.StringIO()
            with patch.dict(sys.modules, {"IPython.display": display_module}), \
                    patch.object(subprocess, "run", return_value=inspection) as inspect, redirect_stdout(printed):
                exec(compile(inspection_cell(), "inspection-display", "exec"), scope)
            display_module.Image.assert_not_called()
            text = printed.getvalue()
            self.assertIn("Tesla T4", text)
            self.assertIn("No submitted works yet. Watch live drawing in the step 7 viewer. "
                          "The initial blank canvas is normal and is not a submitted work.", text)
            self.assertIn("<details>", display_module.HTML.call_args.args[0])
            self.assertEqual("inspect", inspect.call_args.args[0][2])


if __name__ == "__main__":
    unittest.main()
