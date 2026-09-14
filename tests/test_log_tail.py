import random
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import launcher
from log_tail import read_log_tail


class LogTailTests(unittest.TestCase):
    def test_matches_text_reader_for_unicode_newlines_and_invalid_utf8(self):
        rng = random.Random(713)
        samples = [
            b"", b"hello\r\nworld\r\n", "🦙漢é\r\n".encode() * 100,
            b"\xff\xf0\x9f\x92\r\n\xed\xa0\x80" * 100,
            b"before\r" + b"\n" * 400,
        ] + [rng.randbytes(1000) for _ in range(40)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "engine.log"
            for data in samples:
                path.write_bytes(data)
                expected = path.read_text(encoding="utf-8", errors="replace")
                for limit in (1, 2, 3, 7, 31, 249, 1000, 2000):
                    with self.subTest(limit=limit, data=data[:20]):
                        self.assertEqual(read_log_tail(path, limit), expected[-limit:])

    def test_large_sparse_log_does_not_allocate_its_full_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "engine.log"
            suffix = "completed 🦙\r\n" * 5000
            with path.open("wb") as handle:
                handle.seek(256 * 1024 * 1024)
                handle.write(suffix.encode())
            tracemalloc.start()
            try:
                result = read_log_tail(path, 40_000)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertEqual(result, suffix.replace("\r\n", "\n")[-40_000:])
            self.assertLess(peak, 3 * 1024 * 1024,
                            "Preview memory must stay bounded independently of log size")

    def test_missing_unreadable_and_empty_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(read_log_tail(Path(directory) / "missing", 10), "")
            self.assertEqual(read_log_tail(Path(directory), 10), "")
        path = mock.Mock()
        path.open.side_effect = PermissionError()
        self.assertEqual(read_log_tail(path, 10), "")
        path.reset_mock()
        self.assertEqual(read_log_tail(path, 0), "")
        path.open.assert_not_called()

    def test_all_preview_consumers_preserve_limits_and_whitespace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "engine.log"
            text = "start\n" + "🦙 entry\r\n" * 260_000 + " end  \n"
            path.write_bytes(text.encode())
            normalized = text.replace("\r\n", "\n")
            for manager in (launcher.SetupManager, launcher.ModelAcquisitionManager,
                            launcher.RuntimeUpdateManager):
                self.assertEqual(manager._log_tail(path), normalized[-2000:].strip())
            plan = SimpleNamespace(run_dir=root)
            self.assertEqual(launcher.ANETunerManager._read_engine_log(plan),
                             normalized[-2_000_000:])
            handler = SimpleNamespace(path="/api/log", allowed=lambda: True,
                                      json_response=mock.Mock())
            with mock.patch.object(launcher, "MANAGER", SimpleNamespace(plan=plan)):
                launcher.Handler.do_GET(handler)
            handler.json_response.assert_called_once_with({"log": normalized[-40_000:]})
            handler.json_response.reset_mock()
            with mock.patch.object(launcher, "MANAGER", SimpleNamespace(plan=None)):
                launcher.Handler.do_GET(handler)
            handler.json_response.assert_called_once_with({"log": ""})


if __name__ == "__main__":
    unittest.main()
