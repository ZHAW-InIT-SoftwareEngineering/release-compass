import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from pydantic import AnyHttpUrl

from src.configs.trace.trace_config import TraceConfig
from src.harness.trace.phoenix import phoenix_server


class PhoenixServerTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        log_patch = patch(
            "src.harness.trace.phoenix.PHOENIX_LOG_PATH",
            Path(directory.name) / "phoenix.log",
        )
        log_patch.start()
        self.addCleanup(log_patch.stop)

    def test_remote_disabled_or_manual_endpoints_are_not_started(self):
        for config in (
            TraceConfig(endpoint=AnyHttpUrl("https://phoenix.example.com/v1/traces")),
            TraceConfig(enabled=False),
            TraceConfig(auto_start=False),
        ):
            with (
                self.subTest(config=config),
                patch("src.harness.trace.phoenix.subprocess.Popen") as start,
                phoenix_server(config),
            ):
                pass
            start.assert_not_called()

    def test_ready_server_is_reused(self):
        with (
            patch("src.harness.trace.phoenix._is_ready", return_value=True),
            patch("src.harness.trace.phoenix.subprocess.Popen") as start,
            phoenix_server(TraceConfig()),
        ):
            pass
        start.assert_not_called()

    def test_started_server_is_stopped_on_exit(self):
        process = Mock()
        process.poll.return_value = None
        with (
            patch(
                "src.harness.trace.phoenix._is_ready", side_effect=[False, False, True]
            ),
            patch("src.harness.trace.phoenix.sleep"),
            patch("src.harness.trace.phoenix.subprocess.Popen", return_value=process),
            patch("builtins.print"),
            phoenix_server(TraceConfig()),
        ):
            pass
        process.terminate.assert_called_once()

    def test_startup_timeout_stops_process(self):
        process = Mock()
        process.poll.return_value = None
        with (
            patch("src.harness.trace.phoenix._is_ready", return_value=False),
            patch("src.harness.trace.phoenix.monotonic", side_effect=[0, 31]),
            patch("src.harness.trace.phoenix.subprocess.Popen", return_value=process),
            patch("builtins.print"),
            self.assertRaisesRegex(RuntimeError, "Phoenix startup timed out"),
            phoenix_server(TraceConfig()),
        ):
            pass
        process.terminate.assert_called_once()

    def test_exited_process_reports_startup_failure(self):
        process = Mock()
        process.poll.return_value = 1
        with (
            patch("src.harness.trace.phoenix._is_ready", return_value=False),
            patch("src.harness.trace.phoenix.subprocess.Popen", return_value=process),
            patch("builtins.print"),
            self.assertRaisesRegex(RuntimeError, "Phoenix exited during startup"),
            phoenix_server(TraceConfig()),
        ):
            pass
        process.terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
