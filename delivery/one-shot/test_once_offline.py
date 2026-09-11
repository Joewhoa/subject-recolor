from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


SCRIPT = Path(__file__).with_name("一次性换色.py")
SPEC = importlib.util.spec_from_file_location("once_recolor", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class OneShotTests(unittest.TestCase):
    def test_hex_and_prompt(self) -> None:
        color = MODULE.color_from_hex("#2F6B63")
        self.assertEqual(color["rgb"], [47, 107, 99])
        default_prompt = MODULE.build_prompt("沙发", color)
        profile_a_prompt = MODULE.build_prompt("沙发", color, "A")
        self.assertIn("#2F6B63", default_prompt)
        self.assertNotEqual(profile_a_prompt, default_prompt)
        with self.assertRaises(MODULE.FatalError):
            MODULE.build_prompt("沙发", color, "A+B")

        with patch("sys.argv", ["once"]):
            self.assertEqual(MODULE.parse_args().profile, "B")
        with patch("sys.argv", ["once", "--profile", "A"]):
            self.assertEqual(MODULE.parse_args().profile, "A")

    def test_review_uses_relative_source_and_card_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input" / "source.jpg"
            card = root / "cards" / "card.png"
            result = root / "result" / "out.jpg"
            html = root / "result" / "review.html"
            source.parent.mkdir()
            card.parent.mkdir()
            result.parent.mkdir()
            Image.new("RGB", (40, 30), "black").save(source)
            Image.new("RGB", (20, 20), "teal").save(card)
            Image.new("RGB", (40, 30), "teal").save(result)
            MODULE.write_review_html(
                html,
                source,
                str(card),
                result,
                "#008080",
                "沙发",
                "succeeded",
                "rid",
                "A参考方案",
            )
            text = html.read_text(encoding="utf-8")
            self.assertIn("../input/source.jpg", text)
            self.assertIn("../cards/card.png", text)
            self.assertIn("out.jpg", text)
            self.assertIn("Prompt方案", text)
            self.assertIn("A参考方案", text)

    def test_missing_base_url_blocks_paid_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.jpg"
            Image.new("RGB", (40, 30), "black").save(source)
            argv = ["once", str(source), "--hex", "#2F6B63", "--yes", "--base-url", ""]
            with patch("sys.argv", argv):
                self.assertEqual(MODULE.main(), 2)

            model_png = root / "model.png"
            Image.new("RGB", (40, 30), "teal").save(model_png)
            payload = json.dumps(
                {"model": "fake", "data": [{"b64_json": base64.b64encode(model_png.read_bytes()).decode()}]}
            ).encode()
            all_request_ids = []
            all_commands = []

            def run_profile(profile, responses, out, dry_run=False):
                def fake_run(command, **_kwargs):
                    all_commands.append(command)
                    header_path = Path(command[command.index("--header") + 1][1:])
                    request_line = next(
                        line for line in header_path.read_text(encoding="utf-8").splitlines()
                        if line.lower().startswith("x-client-request-id:")
                    )
                    all_request_ids.append(request_line.split(":", 1)[1].strip())
                    response = responses.pop(0)
                    if isinstance(response, Exception):
                        raise response
                    status, body, returncode = response
                    Path(command[command.index("--output") + 1]).write_bytes(body)
                    return subprocess.CompletedProcess(command, returncode, stdout=str(status).encode(), stderr=b"")

                profile_argv = [
                    "once", str(source), "--hex", "#2F6B63", "--yes",
                    "--base-url", "https://offline.invalid", "--out", str(out), "--profile", profile,
                ]
                if dry_run:
                    profile_argv.append("--dry-run")
                with patch("sys.argv", profile_argv), patch.dict(
                    MODULE.os.environ, {"SUB2API_API_KEY": "secret-key"}, clear=False
                ), patch.object(MODULE.shutil, "which", return_value="curl"), patch.object(
                    MODULE.subprocess, "run", side_effect=fake_run
                ), patch.object(MODULE.time, "sleep"):
                    return MODULE.main()

            out = root / "results"
            self.assertEqual(run_profile("A", [(200, payload, 0)], out), 0)
            self.assertEqual(run_profile("B", [(429, b"", 0), (200, payload, 0)], out), 0)
            self.assertEqual(len(all_request_ids), 3)
            self.assertEqual(len(set(all_request_ids)), 3)
            self.assertFalse(any("secret-key" in argument for command in all_commands for argument in command))

            records = sorted(out.glob("*_结果.json"))
            self.assertEqual(len(records), 2)
            self.assertNotEqual(records[0].name, records[1].name)
            profiles = {json.loads(path.read_text(encoding="utf-8"))["profile"] for path in records}
            self.assertEqual(profiles, {"A", "B"})
            reviews = [path.read_text(encoding="utf-8") for path in out.glob("*_审阅.html")]
            self.assertTrue(any("A参考方案" in text for text in reviews))
            self.assertTrue(any("B增强方案" in text for text in reviews))

            b_artifacts = {
                path: path.read_bytes()
                for path in out.glob("source__2F6B63__B*")
            }
            self.assertEqual(len(b_artifacts), 5)
            before_calls = len(all_commands)
            before_request_ids = list(all_request_ids)
            self.assertEqual(run_profile("B", [], out, dry_run=True), 0)
            self.assertEqual(run_profile("B", [], out, dry_run=True), 0)
            self.assertEqual(len(all_commands), before_calls)
            self.assertEqual(all_request_ids, before_request_ids)
            self.assertNotEqual(run_profile("B", [(200, payload, 0)], out), 0)
            self.assertEqual(len(all_commands), before_calls)
            self.assertEqual(all_request_ids, before_request_ids)
            self.assertEqual(
                {path: path.read_bytes() for path in b_artifacts},
                b_artifacts,
            )

            before_calls = len(all_commands)
            self.assertEqual(run_profile("B", [(503, b"", 0)], root / "503"), 3)
            self.assertEqual(len(all_commands) - before_calls, 1)
            before_calls = len(all_commands)
            self.assertEqual(run_profile("B", [OSError("launch blocked")], root / "oserror"), 3)
            self.assertEqual(len(all_commands) - before_calls, 1)


if __name__ == "__main__":
    unittest.main()
