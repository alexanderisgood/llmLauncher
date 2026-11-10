"""Unit coverage for the Splash helper (`tools/run_splash_128k.py`).

The helper exists because the `splash` CLI hardcodes 127.0.0.1:8000 and refuses
to start when another service owns it; these tests pin the argv construction and
the fail-closed package checks without ever starting the engine.
"""
from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import pathlib
import socket
import sys
import tempfile
import unittest
from unittest import mock

from test_splash_runtime import write_pack, write_install

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_helper():
    spec = importlib.util.spec_from_file_location(
        "run_splash_128k", ROOT / "tools" / "run_splash_128k.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SplashRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.helper = load_helper()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.models = pathlib.Path(self.tmp.name)

    def make_pack(self, model: str = "owner/pack", *, artifacts: int = 3) -> pathlib.Path:
        owner, repo = model.split("/")
        return write_pack(self.models, owner=owner, repo=repo)

    def test_pack_ready_accepts_a_complete_package(self) -> None:
        root = self.make_pack(artifacts=78)
        ready, detail = self.helper.pack_ready(root)
        self.assertTrue(ready)
        self.assertIn("artifact paths and sizes checked", detail)

    def test_pack_ready_fails_closed_on_missing_pieces(self) -> None:
        root = self.models / "owner" / "pack"
        root.mkdir(parents=True)
        ready, detail = self.helper.pack_ready(root)
        self.assertFalse(ready)
        self.assertIn("manifest.json", detail)

        self.make_pack("owner/partial")
        (self.models / "owner/partial/draft/model.bin").unlink()
        ready, detail = self.helper.pack_ready(self.models / "owner/partial")
        self.assertFalse(ready)
        self.assertIn("draft", detail)

        broken = self.models / "owner/broken"
        broken.mkdir(parents=True)
        (broken / "manifest.json").write_text("{not json", encoding="utf-8")
        ready, detail = self.helper.pack_ready(broken)
        self.assertFalse(ready)
        self.assertIn("invalid manifest", detail)

    def test_build_argv_pins_the_pack_paths_and_port(self) -> None:
        pack = self.make_pack()
        argv = self.helper.build_argv(
            "owner/pack", port=8011, context=131072,
            libexec=pathlib.Path("/tmp/libexec"), models=self.models,
        )
        self.assertEqual(argv[0], "/tmp/libexec/python/bin/python3")
        self.assertTrue(argv[2].endswith("/splash_reasoning.py"))
        self.assertEqual(argv[3], "/tmp/libexec/server/server.py")
        self.assertEqual(argv[4], str(pack / "target"))
        self.assertEqual(argv[5], str(pack / "draft"))
        index = argv.index("--tokenizer")
        self.assertEqual(argv[index + 1], str(pack / "tokenizer"))
        self.assertEqual(argv[argv.index("--port") + 1], "8011")
        self.assertEqual(argv[argv.index("--max-context") + 1], "131072")
        self.assertEqual(argv[argv.index("--max-memory") + 1], "auto")
        self.assertIn("--no-webui", argv)

    def test_free_port_skips_a_busy_port(self) -> None:
        with socket.socket() as busy:
            busy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                busy.bind(("127.0.0.1", 0))
            except PermissionError:
                # The sandbox blocks socket binds (same reason the suite's
                # socket cases error here and pass outside it).
                self.skipTest("socket binding is not permitted in this sandbox")
            busy.listen(1)
            taken = busy.getsockname()[1]
            self.assertNotEqual(self.helper.free_port(taken, tries=5), taken)

    def test_model_root_is_bound_to_the_repo_convention(self) -> None:
        pack = self.make_pack("incoai/Qwen3.8-27B-Splash")
        self.assertEqual(
            self.helper.model_root("incoai/Qwen3.8-27B-Splash", self.models), pack,
        )
        for model in ("../../outside", "/tmp/pack", "owner/../pack"):
            with self.assertRaises(ValueError):
                self.helper.model_root(model, self.models)

    def test_check_rejects_missing_python_and_missing_artifacts(self):
        libexec = write_install(self.models / "install")
        pack = self.make_pack()
        with mock.patch.object(self.helper, "LIBEXEC", libexec), \
                mock.patch.object(self.helper, "MODELS", self.models), \
                mock.patch.object(self.helper, "verify_frontend"), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.helper.main(["--model", "owner/pack", "--check"]), 0)
            (pack / "target/layer-0.bin").unlink()
            self.assertEqual(self.helper.main(["--model", "owner/pack", "--check"]), 2)
            (libexec / "python/bin/python3").unlink()
            self.assertEqual(self.helper.main(["--model", "owner/pack", "--check"]), 2)

    def test_readiness_authenticates_and_rejects_wrong_model(self):
        process = mock.Mock()
        process.poll.return_value = None
        def response(request, timeout):
            self.assertEqual(request.get_header("Authorization"), "Bearer fixture-key")
            return io.BytesIO(json.dumps({"data": [{"id": "owner/pack"}]}).encode())
        with mock.patch.object(self.helper.urllib.request, "urlopen", side_effect=response):
            catalog = self.helper.wait_ready(8010, process, 1, "fixture-key", "owner/pack")
            self.assertEqual(catalog["data"][0]["id"], "owner/pack")
            with mock.patch.object(self.helper.time, "monotonic", side_effect=[0, 0, 2]), \
                    mock.patch.object(self.helper.time, "sleep"), self.assertRaises(SystemExit):
                self.helper.wait_ready(8010, process, 1, "fixture-key", "different/pack")

    def test_host_passes_key_privately_and_cleans_up_on_readiness_failure(self):
        libexec = write_install(self.models / "install")
        self.make_pack()
        captured = {}
        process = mock.Mock(returncode=-15)
        process.poll.return_value = None
        def start(argv, **kwargs):
            captured.update(argv=argv, env=kwargs["env"])
            self.assertNotIn("fixture-key", argv)
            self.assertEqual(kwargs["env"]["SPLASH_API_KEY"], "fixture-key")
            return process
        with mock.patch.object(self.helper, "LIBEXEC", libexec), \
                mock.patch.object(self.helper, "MODELS", self.models), \
                mock.patch.object(self.helper, "verify_frontend"), \
                mock.patch.object(self.helper, "free_port", return_value=8010), \
                mock.patch.dict(self.helper.os.environ, {"SPLASH_API_KEY": "fixture-key"}), \
                mock.patch.object(self.helper.subprocess, "Popen", side_effect=start), \
                mock.patch.object(self.helper, "wait_ready", side_effect=SystemExit("not ready")), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            self.helper.main(["--model", "owner/pack"])
        self.assertTrue(any(arg.endswith("splash_reasoning.py") for arg in captured["argv"]))
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=20)


if __name__ == "__main__":
    unittest.main()
