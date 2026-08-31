from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import subprocess

from PIL import Image

from recolor.api.image_edit_client import (
    APIResult,
    FatalError,
    ImageEditClient,
    SafeRetryError,
    UncertainError,
)
from recolor.config import Settings
from recolor.core.images import prepare_upload, repair_jpg, save_model_outputs
from recolor.core.processor import BatchProcessor, build_plan
from recolor.core.prompt_builder import build_prompt, extract_color
from recolor.utils.files import sha256_file, valid_output_image


class OfflinePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "待处理").mkdir()
        (self.root / "色卡").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _image(self, path: Path, color: tuple[int, int, int], size=(400, 300)) -> Path:
        Image.new("RGB", size, color).save(path, quality=96)
        return path

    def test_center_color_and_prompt(self) -> None:
        card = self._image(self.root / "色卡" / "navy.jpg", (24, 43, 58), (400, 400))
        color = extract_color(card)
        self.assertEqual(color["rgb"], [24, 43, 58])
        self.assertEqual(color["hex"], "#182B3A")
        prompt = build_prompt("户外窗帘", color, "B")
        self.assertIn("#182B3A", prompt)
        self.assertIn("所有可见的户外窗帘", prompt)
        self.assertIn("不得改变构图", prompt)

    def test_cartesian_plan_and_checkpoint(self) -> None:
        self._image(self.root / "待处理" / "one.jpg", (220, 210, 200))
        self._image(self.root / "待处理" / "two.png", (180, 170, 160))
        self._image(self.root / "色卡" / "a.jpg", (20, 40, 60))
        self._image(self.root / "色卡" / "b.jpg", (200, 210, 220))
        settings = Settings(profile="B")
        plan = build_plan(self.root, settings)
        self.assertEqual(len(plan.tasks), 4)
        self.assertEqual(len(plan.contexts), 2)
        for context in plan.contexts:
            context_tasks = [task for task in plan.tasks if task["context_id"] == context["context_id"]]
            self.assertEqual(len(context_tasks), 2)
            self.assertEqual({task["source"] for task in context_tasks}, {context["source"]})
        processor = BatchProcessor(plan, settings)
        self.assertEqual(processor.preview()["new_api_calls"], 4)
        checkpoint = json.loads((plan.records_dir / "checkpoint_profile_B.json").read_text("utf-8"))
        self.assertEqual(len(checkpoint["tasks"]), 4)

    def test_duplicate_stems_are_rejected(self) -> None:
        self._image(self.root / "待处理" / "Scene.jpg", (10, 20, 30))
        self._image(self.root / "待处理" / "scene.png", (20, 30, 40))
        self._image(self.root / "色卡" / "navy.jpg", (24, 43, 58))
        with self.assertRaisesRegex(ValueError, "重复文件主名"):
            build_plan(self.root, Settings())

    def test_b_is_default_and_a_is_explicitly_supported(self) -> None:
        default = Settings()
        default.validate()
        self.assertEqual(default.profile, "B")
        alternate = Settings(profile="A")
        alternate.validate()
        color = {"rgb": [24, 43, 58], "hex": "#182B3A", "description": "深蓝色"}
        self.assertNotEqual(build_prompt("户外窗帘", color, "A"), build_prompt("户外窗帘", color, "B"))
        for allowed in (0, 1):
            Settings(max_safe_retries=allowed).validate()
        for forbidden in (-1, 2, 3):
            with self.assertRaisesRegex(ValueError, "只能是 0 或 1"):
                Settings(max_safe_retries=forbidden).validate()

    def test_a_and_b_are_isolated(self) -> None:
        self._image(self.root / "待处理" / "one.jpg", (220, 210, 200))
        self._image(self.root / "色卡" / "navy.jpg", (24, 43, 58))
        plan_a = build_plan(self.root, Settings(profile="A"))
        plan_b = build_plan(self.root, Settings(profile="B"))
        self.assertNotEqual(plan_a.tasks[0]["task_id"], plan_b.tasks[0]["task_id"])
        self.assertNotEqual(plan_a.tasks[0]["png"], plan_b.tasks[0]["png"])

    def test_compression_does_not_modify_source(self) -> None:
        source = self._image(self.root / "待处理" / "large.jpg", (120, 80, 40), (2600, 1800))
        before = sha256_file(source)
        settings = Settings(upload_max_dimension=1000, upload_max_bytes=500_000)
        prepared = prepare_upload(source, self.root / "cache", settings)
        self.assertEqual(before, sha256_file(source))
        self.assertLessEqual(max(prepared.upload_size), 1000)
        self.assertLessEqual(prepared.upload_bytes, 500_000)
        self.assertTrue(valid_output_image(Path(prepared.upload_path)))

    def test_png_master_and_jpg_repair(self) -> None:
        png_buffer = Path(self.root / "model.png")
        Image.new("RGB", (640, 480), (12, 34, 56)).save(png_buffer)
        raw = png_buffer.read_bytes()
        png = self.root / "out" / "result.png"
        jpg = self.root / "out" / "result.jpg"
        size = save_model_outputs(raw, png, jpg, 85)
        self.assertEqual(size, (640, 480))
        self.assertEqual(png.read_bytes(), raw)
        self.assertTrue(valid_output_image(jpg))
        jpg.unlink()
        self.assertEqual(repair_jpg(png, jpg, 85), (640, 480))
        self.assertTrue(valid_output_image(jpg))

    def test_end_to_end_fake_api_and_resume(self) -> None:
        self._image(self.root / "待处理" / "scene.jpg", (180, 160, 140))
        self._image(self.root / "色卡" / "a.jpg", (20, 40, 60))
        self._image(self.root / "色卡" / "b.jpg", (200, 210, 220))
        settings = Settings(profile="B", pause_between_tasks=0, retry_delay_seconds=0)
        plan = build_plan(self.root, settings)
        processor = BatchProcessor(plan, settings)
        model_png = self.root / "fake_model.png"
        Image.new("RGB", (400, 300), (30, 50, 70)).save(model_png)
        raw = model_png.read_bytes()

        class FakeClient:
            calls = 0

            def __init__(self, *_args, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def edit(self, *_args, **_kwargs):
                FakeClient.calls += 1
                return APIResult(raw, {"model": "fake"})

            def reconnect(self):
                pass

        with patch("recolor.core.processor.ImageEditClient", FakeClient):
            counts = processor.run("fake-key")
        self.assertEqual(FakeClient.calls, 2)
        self.assertEqual(counts.get("succeeded"), 2)

        resumed = BatchProcessor(build_plan(self.root, settings), settings)
        with patch("recolor.core.processor.ImageEditClient", FakeClient):
            resumed_counts = resumed.run("fake-key")
        self.assertEqual(FakeClient.calls, 2, "resume should not call the API again")
        self.assertEqual(resumed_counts.get("succeeded"), 2)

    def test_uncertain_stops_remaining_tasks(self) -> None:
        self._image(self.root / "待处理" / "scene.jpg", (180, 160, 140))
        self._image(self.root / "色卡" / "a.jpg", (20, 40, 60))
        self._image(self.root / "色卡" / "b.jpg", (200, 210, 220))
        settings = Settings(profile="B", pause_between_tasks=0)
        processor = BatchProcessor(build_plan(self.root, settings), settings)

        class UncertainClient:
            calls = 0

            def __init__(self, *_args, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def edit(self, *_args, **_kwargs):
                UncertainClient.calls += 1
                raise UncertainError("simulated read timeout")

            def reconnect(self):
                pass

        with patch("recolor.core.processor.ImageEditClient", UncertainClient):
            counts = processor.run("fake-key")
        self.assertEqual(UncertainClient.calls, 1)
        self.assertEqual(counts.get("uncertain"), 1)
        self.assertEqual(counts.get("pending"), 1)

        task_id = processor.plan.tasks[0]["task_id"]
        first_state = processor.checkpoint.task(task_id)
        first_request_id = first_state["request_ids"][0]
        self.assertEqual(first_state["attempts"], 1)

        model_png = self.root / "retry_success.png"
        Image.new("RGB", (400, 300), (30, 50, 70)).save(model_png)
        raw = model_png.read_bytes()

        class SuccessClient(UncertainClient):
            request_ids = []

            def edit(self, _upload, _prompt, request_id):
                self.request_ids.append(request_id)
                return APIResult(raw, {"model": "retry-success"})

        with patch("recolor.core.processor.ImageEditClient", SuccessClient):
            success_processor = BatchProcessor(build_plan(self.root, settings), settings)
            success_counts = success_processor.run("fake-key", limit=1, retry_uncertain=True)
        success_state = success_processor.checkpoint.task(task_id)
        self.assertEqual(success_counts.get("succeeded"), 1)
        self.assertEqual(success_state["attempts"], 2)
        self.assertEqual(success_state["request_ids"], [first_request_id, SuccessClient.request_ids[0]])

        events_path = success_processor.checkpoint.events_path
        events = [json.loads(line) for line in events_path.read_text("utf-8").splitlines()]
        submitted = [event for event in events if event.get("task_id") == task_id and event["status"] == "submitted"]
        self.assertEqual([event["attempt"] for event in submitted], [1, 2])
        self.assertEqual([event["request_id"] for event in submitted], success_state["request_ids"])

        summary_path = success_processor.plan.records_dir / "summary_profile_B.csv"
        with summary_path.open(encoding="utf-8-sig", newline="") as input_file:
            success_row = next(csv.DictReader(input_file))
        self.assertEqual(success_row["attempts"], "2")
        self.assertEqual(success_row["request_ids"].split(" | "), success_state["request_ids"])

        failure_root = self.root / "explicit_retry_failure"
        (failure_root / "待处理").mkdir(parents=True)
        (failure_root / "色卡").mkdir()
        self._image(failure_root / "待处理" / "scene.jpg", (180, 160, 140))
        self._image(failure_root / "色卡" / "a.jpg", (20, 40, 60))
        failure_settings = Settings(profile="B", pause_between_tasks=0, retry_delay_seconds=0, max_safe_retries=1)
        failure_processor = BatchProcessor(build_plan(failure_root, failure_settings), failure_settings)
        with patch("recolor.core.processor.ImageEditClient", UncertainClient):
            failure_processor.run("fake-key")
        failure_task_id = failure_processor.plan.tasks[0]["task_id"]
        failure_first_id = failure_processor.checkpoint.task(failure_task_id)["request_ids"][0]

        class FailureClient(UncertainClient):
            request_ids = []

            def edit(self, _upload, _prompt, request_id):
                self.request_ids.append(request_id)
                raise SafeRetryError("429 or connection not established")

        with patch("recolor.core.processor.ImageEditClient", FailureClient):
            retried_failure = BatchProcessor(build_plan(failure_root, failure_settings), failure_settings)
            failure_counts = retried_failure.run("fake-key", retry_uncertain=True)
        failure_state = retried_failure.checkpoint.task(failure_task_id)
        self.assertEqual(failure_counts.get("failed_safe"), 1)
        self.assertEqual(failure_state["attempts"], 3)
        self.assertEqual(failure_state["request_ids"], [failure_first_id, *FailureClient.request_ids])
        self.assertEqual(len(FailureClient.request_ids), 2, "automatic retry remains capped per invocation")

        failure_events = [
            json.loads(line) for line in retried_failure.checkpoint.events_path.read_text("utf-8").splitlines()
        ]
        failure_submitted = [
            event for event in failure_events
            if event.get("task_id") == failure_task_id and event["status"] == "submitted"
        ]
        self.assertEqual([event["attempt"] for event in failure_submitted], [1, 2, 3])
        with (retried_failure.plan.records_dir / "summary_profile_B.csv").open(
            encoding="utf-8-sig", newline=""
        ) as input_file:
            failure_row = next(csv.DictReader(input_file))
        self.assertEqual(failure_row["attempts"], "3")
        self.assertEqual(failure_row["request_ids"].split(" | "), failure_state["request_ids"])

        class RetryClient(UncertainClient):
            request_ids = []
            mode = "safe"

            def edit(self, _upload, _prompt, request_id):
                self.request_ids.append(request_id)
                if self.mode == "fatal":
                    raise FatalError("curl launch OSError")
                raise SafeRetryError("429 or connection not established")

        for retry_cap, expected_calls in ((0, 1), (1, 2)):
            retry_settings = Settings(
                profile="B", pause_between_tasks=0, retry_delay_seconds=0, max_safe_retries=retry_cap
            )
            RetryClient.request_ids = []
            RetryClient.mode = "safe"
            with patch("recolor.core.processor.ImageEditClient", RetryClient):
                retry_counts = BatchProcessor(build_plan(self.root, retry_settings), retry_settings).run("fake-key")
            self.assertEqual(len(RetryClient.request_ids), expected_calls)
            self.assertEqual(len(set(RetryClient.request_ids)), expected_calls)
            self.assertEqual(retry_counts.get("failed_safe"), 1)

            retry_root = self.root / f"fatal_{retry_cap}"
            (retry_root / "待处理").mkdir(parents=True)
            (retry_root / "色卡").mkdir()
            self._image(retry_root / "待处理" / "scene.jpg", (180, 160, 140))
            self._image(retry_root / "色卡" / "a.jpg", (20, 40, 60))
            RetryClient.request_ids = []
            RetryClient.mode = "fatal"
            fatal_processor = BatchProcessor(build_plan(retry_root, retry_settings), retry_settings)
            with patch("recolor.core.processor.ImageEditClient", RetryClient):
                fatal_counts = fatal_processor.run("fake-key")
            self.assertEqual(len(RetryClient.request_ids), 1)
            self.assertEqual(fatal_counts.get("rejected"), 1)

    def test_many_sources_reconnect_between_isolated_contexts(self) -> None:
        for index in range(3):
            self._image(self.root / "待处理" / f"scene_{index}.jpg", (150 + index, 140, 130))
        self._image(self.root / "色卡" / "a.jpg", (20, 40, 60))
        self._image(self.root / "色卡" / "b.jpg", (200, 210, 220))
        settings = Settings(profile="B", pause_between_tasks=0)
        processor = BatchProcessor(build_plan(self.root, settings), settings)
        model_png = self.root / "fake_context_result.png"
        Image.new("RGB", (400, 300), (30, 50, 70)).save(model_png)
        raw = model_png.read_bytes()

        class ContextClient:
            uploaded_names = []
            reconnects = 0

            def __init__(self, *_args, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def edit(self, upload_path, *_args, **_kwargs):
                self.uploaded_names.append(upload_path.name)
                return APIResult(raw, {"model": "fake"})

            def reconnect(self):
                type(self).reconnects += 1

        with patch("recolor.core.processor.ImageEditClient", ContextClient):
            counts = processor.run("fake-key")

        self.assertEqual(counts.get("succeeded"), 6)
        self.assertEqual(ContextClient.reconnects, 2)
        groups = [ContextClient.uploaded_names[index:index + 2] for index in range(0, 6, 2)]
        self.assertTrue(all(len(set(group)) == 1 for group in groups))
        self.assertEqual(len({group[0] for group in groups}), 3)

    def test_curl_transport_success_without_network(self) -> None:
        import base64

        source = self._image(self.root / "upload.jpg", (10, 20, 30))
        model_png = self.root / "fake_curl.png"
        Image.new("RGB", (64, 48), (40, 50, 60)).save(model_png)
        payload = json.dumps({"model": "fake", "data": [{"b64_json": base64.b64encode(model_png.read_bytes()).decode()}]}).encode()

        captured_commands = []

        def fake_run(command, **_kwargs):
            captured_commands.append(command)
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_bytes(payload)
            return subprocess.CompletedProcess(command, 0, stdout=b"200", stderr=b"")

        with patch("recolor.api.image_edit_client.shutil.which", return_value="/usr/bin/curl"), patch(
            "recolor.api.image_edit_client.subprocess.run", side_effect=fake_run
        ):
            result = ImageEditClient(Settings(), "fake-key").edit(source, "prompt", "request-id")
        self.assertEqual(result.image_bytes, model_png.read_bytes())
        self.assertEqual(result.metadata["transport"], "system-curl")
        argv = captured_commands[0]
        self.assertFalse(any("fake-key" in argument for argument in argv))
        self.assertTrue(argv[argv.index("--header") + 1].startswith("@"))

        with patch("recolor.api.image_edit_client.shutil.which", return_value="/usr/bin/curl"), patch(
            "recolor.api.image_edit_client.subprocess.run", side_effect=OSError("launch blocked")
        ) as run:
            with self.assertRaises(FatalError):
                ImageEditClient(Settings(), "argv-secret").edit(source, "prompt", "request-id")
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[0]
        self.assertFalse(any("argv-secret" in argument for argument in command))

    def test_curl_transport_empty_503_is_uncertain(self) -> None:
        source = self._image(self.root / "upload.jpg", (10, 20, 30))
        calls = []

        def fake_run(command, **_kwargs):
            calls.append(command)
            Path(command[command.index("--output") + 1]).write_bytes(b"")
            return subprocess.CompletedProcess(command, 0, stdout=b"503", stderr=b"")

        with patch("recolor.api.image_edit_client.shutil.which", return_value="/usr/bin/curl"), patch(
            "recolor.api.image_edit_client.subprocess.run", side_effect=fake_run
        ):
            with self.assertRaises(UncertainError) as caught:
                ImageEditClient(Settings(), "fake-key").edit(source, "prompt", "request-id")
        self.assertEqual(caught.exception.http_status, 503)
        self.assertEqual(len(calls), 1)

        for returncode, stdout, error_type in (
            (0, b"429", SafeRetryError),
            (6, b"000", SafeRetryError),
        ):
            def classified_run(command, **_kwargs):
                Path(command[command.index("--output") + 1]).write_bytes(b"")
                return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=b"offline")

            with patch("recolor.api.image_edit_client.shutil.which", return_value="/usr/bin/curl"), patch(
                "recolor.api.image_edit_client.subprocess.run", side_effect=classified_run
            ):
                with self.assertRaises(error_type):
                    ImageEditClient(Settings(), "fake-key").edit(source, "prompt", "request-id")


if __name__ == "__main__":
    unittest.main()
