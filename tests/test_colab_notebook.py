"""Offline release checks for executable notebook safety and portability."""
import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


class ColabNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads((ROOT / "notebooks/RobotPainting_Colab.ipynb").read_text("utf-8"))
        cls.code = ["".join(cell["source"]) for cell in cls.notebook["cells"] if cell["cell_type"] == "code"]

    def test_notebook_is_output_free_and_all_code_compiles(self):
        self.assertEqual((4, 5), (self.notebook["nbformat"], self.notebook["nbformat_minor"]))
        identifiers = []
        for cell in self.notebook["cells"]:
            self.assertIn(cell["cell_type"], ("markdown", "code"))
            self.assertIsInstance(cell["metadata"], dict)
            self.assertTrue(all(isinstance(line, str) for line in cell["source"]))
            identifiers.append(cell["id"])
            if cell["cell_type"] == "code":
                self.assertIsNone(cell["execution_count"])
                self.assertEqual([], cell["outputs"])
                compile("".join(cell["source"]), "colab-cell", "exec")
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_paid_process_launch_is_guarded_by_default_false_switch(self):
        start = next(source for source in self.code if "START_EVALUATION =" in source)
        tree = ast.parse(start)
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign))
        self.assertEqual("START_EVALUATION", assignment.targets[0].id)
        self.assertIs(assignment.value.value, False)
        gate = next(node for node in tree.body if isinstance(node, ast.If))
        self.assertIsInstance(gate.test, ast.UnaryOp)
        self.assertIsInstance(gate.test.op, ast.Not)
        self.assertEqual("START_EVALUATION", gate.test.operand.id)
        process_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Attribute) and node.func.attr == "Popen"]
        self.assertEqual(1, len(process_calls))
        self.assertIn(process_calls[0], [node for branch in gate.orelse for node in ast.walk(branch)])
        self.assertIn("evaluation_started.json", start)

    def test_uses_existing_installer_preparer_and_evaluator(self):
        source = "\n".join(self.code)
        for command in ("scripts/install_runtime.py", "scripts/prepare_run.py", "scripts/run_eval.py"):
            self.assertIn(command, source)
        self.assertIn('LOCK["agentark"]["commit"]', source)
        self.assertIn('"benchmarks/versions.json"', source)
        self.assertIn('"3.10.12"', source)
        self.assertIn("getpass.getpass", source)
        self.assertIn('RENDER_MODE = "xvfb-software"', source)
        self.assertNotIn("api_key=", source)
        for private in ("C:/", "/root/", "C:/Users/"):
            self.assertNotIn(private, source)

    def test_current_and_copied_custom_inputs_are_checked_before_credentials_or_processes(self):
        helper_source = next(source for source in self.code if "def input_identity" in source)
        functions = [node for node in ast.parse(helper_source).body if isinstance(node, ast.FunctionDef)]
        start_source = next(source for source in self.code if "START_EVALUATION =" in source)
        start_tree = ast.parse(start_source)
        next(node for node in start_tree.body if isinstance(node, ast.Assign)).value = ast.Constant(True)
        ast.fix_missing_locations(start_tree)
        for change in ("unchanged", "goal", "custom_text_goal", "image_bytes", "image_order", "copied_goal", "copied_image"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                out = root / "run"
                (out / "inputs").mkdir(parents=True)
                images = [root / "first.png", root / "second.png"]
                for index, image in enumerate(images):
                    image.write_bytes(f"reference-{index}".encode())
                    (out / "inputs" / image.name).write_bytes(image.read_bytes())
                target_mode = "custom_text" if change == "custom_text_goal" else "custom_images"
                scope = {"TARGET_MODE": target_mode, "MODEL": "sol", "CUSTOM_GOAL": "Paint a lighthouse.",
                         "RENDER_MODE": "xvfb-software", "UPLOADED_REFERENCES": images,
                         "RUN": out, "manifest": {"model": {"name": "sol"}},
                         "json": json, "os": os, "subprocess": Mock(), "secret": Mock()}
                exec(compile(ast.Module(body=functions, type_ignores=[]), "notebook-helpers", "exec"), scope)
                identity = scope["selected_input_identity"]()
                (out / "inputs/painting_goal.txt").write_bytes((scope["CUSTOM_GOAL"] + "\n").encode("utf-8"))
                (out / "notebook_runtime.json").write_text(json.dumps({
                    "target_mode": target_mode, "render_mode": "xvfb-software", "selected_inputs": identity}), encoding="utf-8")
                if change in ("goal", "custom_text_goal"):
                    scope["CUSTOM_GOAL"] = "Paint a different goal."
                elif change == "image_bytes":
                    images[0].write_bytes(b"edited-image")
                elif change == "image_order":
                    scope["UPLOADED_REFERENCES"] = list(reversed(images))
                elif change == "copied_goal":
                    (out / "inputs/painting_goal.txt").write_text("Changed copied goal", encoding="utf-8")
                elif change == "copied_image":
                    (out / "inputs" / images[0].name).write_bytes(b"edited-copy")
                scope["subprocess"].run.side_effect = RuntimeError("Reached graphics preflight")
                expected = "Reached graphics preflight" if change == "unchanged" else "inputs changed|input copies changed"
                with self.assertRaisesRegex(RuntimeError, expected):
                    exec(compile(start_tree, "notebook-start", "exec"), scope)
                scope["secret"].assert_not_called()
                scope["subprocess"].Popen.assert_not_called()
                self.assertFalse((out / "evaluation_started.json").exists())
                self.assertEqual(1 if change == "unchanged" else 0, scope["subprocess"].run.call_count)


if __name__ == "__main__":
    unittest.main()
