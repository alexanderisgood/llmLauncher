from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def import_file(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


codex_proxy = import_file("proxy_config_codex_proxy", "codex_proxy.py")
session_proxy = import_file("proxy_config_session_proxy", "session_proxy.py")


class ProxyConfigLifetimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="llm-launcher-proxy-config-")
        self.home = Path(self.temp.name) / "home"
        self.runs = (
            self.home / "Library" / "Application Support" / "LLM Launcher" / "runs"
        )
        self.runs.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_dir(self, name: str) -> Path:
        path = self.runs / name
        path.mkdir(mode=0o700)
        path.chmod(0o700)
        return path

    @staticmethod
    def write_private(path: Path, value: object, *, raw: bool = False) -> None:
        data = value if raw else json.dumps(value)
        if isinstance(data, str):
            data = data.encode("utf-8")
        path.write_bytes(data)
        path.chmod(0o600)

    @staticmethod
    def session_value() -> dict[str, object]:
        return {
            "version": 2,
            "listenPort": 18_181,
            "upstreamPort": 18_182,
            "lanes": 1,
            "outputLimit": 512,
            "backend": "omlx",
            "contextLimit": 8_192,
            "reasoning": "auto",
            "reasoningBudgetMessage": None,
            "controlKey": "session-control-" + "a" * 32,
            "upstreamKey": "session-upstream-" + "b" * 32,
            "servedModel": "served-model",
            "surfaces": [{
                "id": str(uuid.uuid4()),
                "client": "pi",
                "key": "surface-secret-" + "c" * 32,
                "samplingContract": {
                    "schemaVersion": 1, "controlled": True, "mode": "model",
                    "values": {"temperature": 0.7},
                },
                "samplingEnforcement": {
                    "protocol": "chat-completions",
                    "representableFields": ["temperature"],
                    "implicitModelDefaults": False,
                },
            }],
        }

    @staticmethod
    def codex_value() -> dict[str, object]:
        return {
            "listenPort": 18_183,
            "upstreamPort": 18_184,
            "outputLimit": 1_024,
            "backend": "omlx",
            "contextLimit": 8_192,
            "reasoning": "auto",
            "clientKey": "codex-client-" + "d" * 32,
            "upstreamKey": "codex-upstream-" + "e" * 32,
            "servedModel": "served-model",
            "templateReasoningEfforts": [],
            "samplingContract": {
                "schemaVersion": 1, "controlled": True, "mode": "model",
                "values": {"temperature": 0.7},
            },
            "samplingEnforcement": {
                "protocol": "responses",
                "representableFields": ["temperature"],
                "implicitModelDefaults": False,
            },
        }

    def load(self, module, path: Path):
        with (
            mock.patch.object(module.Path, "home", return_value=self.home),
            mock.patch.object(module.sys, "stderr", io.StringIO()) as stderr,
        ):
            try:
                return module.load_config(path), stderr.getvalue()
            except SystemExit as error:
                error.stderr = stderr.getvalue()  # type: ignore[attr-defined]
                raise

    def test_valid_configs_are_consumed_and_secrets_stay_out_of_public_status(self) -> None:
        cases = (
            (session_proxy, "session-proxy.json", self.session_value()),
            (codex_proxy, "codex-proxy.json", self.codex_value()),
        )
        for module, filename, value in cases:
            with self.subTest(module=module.__name__):
                path = self.run_dir(module.__name__) / filename
                self.write_private(path, value)
                loaded, stderr = self.load(module, path)
                self.assertFalse(path.exists())
                self.assertEqual(stderr, "")
                self.assertEqual(loaded["upstreamKey"], value["upstreamKey"])
                with self.assertRaises(SystemExit):
                    self.load(module, path)
                self.assertFalse(path.exists())

        session = self.session_value()
        registry = session_proxy.SurfaceRegistry(session["surfaces"])
        public = json.dumps(registry.public())
        for secret in (
            session["controlKey"], session["upstreamKey"],
            session["surfaces"][0]["key"],
        ):
            self.assertNotIn(secret, public)

    def test_main_consumes_config_before_creating_listener(self) -> None:
        cases = (
            (session_proxy, "session-proxy.json", self.session_value()),
            (codex_proxy, "codex-proxy.json", self.codex_value()),
        )
        for module, filename, value in cases:
            with self.subTest(module=module.__name__):
                path = self.run_dir("main-" + module.__name__) / filename
                self.write_private(path, value)
                test_case = self

                class FakeServer:
                    daemon_threads = False

                    def __init__(self, *_args, **_kwargs) -> None:
                        test_case.assertFalse(path.exists())

                    def serve_forever(self, **_kwargs) -> None:
                        return

                    def server_close(self) -> None:
                        return

                with (
                    mock.patch.object(module.Path, "home", return_value=self.home),
                    mock.patch.object(module.sys, "argv", [filename, str(path)]),
                    mock.patch.object(module, "ThreadingHTTPServer", FakeServer),
                ):
                    module.main()
                self.assertFalse(path.exists())

    def test_symlink_and_hardlink_configs_are_rejected_without_following(self) -> None:
        for module, filename, value in (
            (session_proxy, "session-proxy.json", self.session_value()),
            (codex_proxy, "codex-proxy.json", self.codex_value()),
        ):
            for attack in ("symlink", "hardlink"):
                with self.subTest(module=module.__name__, attack=attack):
                    directory = self.run_dir(f"{module.__name__}-{attack}")
                    target = directory / "target.json"
                    path = directory / filename
                    self.write_private(target, value)
                    if attack == "symlink":
                        path.symlink_to(target.name)
                    else:
                        os.link(target, path)
                    secret = str(value["upstreamKey"])
                    with self.assertRaises(SystemExit) as raised:
                        self.load(module, path)
                    self.assertNotIn(secret, getattr(raised.exception, "stderr", ""))
                    self.assertTrue(path.exists() or path.is_symlink())
                    self.assertTrue(target.exists())

    def test_path_replacement_during_read_is_rejected(self) -> None:
        real_read = os.read
        for module, filename, value in (
            (session_proxy, "session-proxy.json", self.session_value()),
            (codex_proxy, "codex-proxy.json", self.codex_value()),
        ):
            with self.subTest(module=module.__name__):
                directory = self.run_dir("replace-" + module.__name__)
                path = directory / filename
                displaced = directory / "displaced.json"
                self.write_private(path, value)
                replacement = dict(value)
                replacement["upstreamKey"] = "replacement-secret-" + "z" * 32
                replaced = False

                def racing_read(descriptor: int, size: int) -> bytes:
                    nonlocal replaced
                    chunk = real_read(descriptor, size)
                    if chunk and not replaced:
                        path.rename(displaced)
                        self.write_private(path, replacement)
                        replaced = True
                    return chunk

                with mock.patch.object(codex_proxy.os, "read", side_effect=racing_read):
                    with self.assertRaises(SystemExit) as raised:
                        self.load(module, path)
                self.assertTrue(replaced)
                self.assertTrue(path.exists())
                self.assertTrue(displaced.exists())
                output = getattr(raised.exception, "stderr", "")
                self.assertNotIn(str(value["upstreamKey"]), output)
                self.assertNotIn(str(replacement["upstreamKey"]), output)

    def test_safely_opened_malformed_configs_are_consumed_without_secret_logs(self) -> None:
        cases = (
            (session_proxy, "session-proxy.json", self.session_value()),
            (codex_proxy, "codex-proxy.json", self.codex_value()),
        )
        for module, filename, value in cases:
            for malformed in ("syntax", "semantic"):
                with self.subTest(module=module.__name__, malformed=malformed):
                    path = self.run_dir(f"malformed-{module.__name__}-{malformed}") / filename
                    secret = str(value["upstreamKey"])
                    if malformed == "syntax":
                        self.write_private(
                            path,
                            ('{"upstreamKey":"' + secret + '","broken":').encode(),
                            raw=True,
                        )
                    else:
                        invalid = dict(value)
                        invalid["listenPort"] = 1
                        self.write_private(path, invalid)
                    with self.assertRaises(SystemExit) as raised:
                        self.load(module, path)
                    self.assertFalse(path.exists())
                    self.assertNotIn(secret, getattr(raised.exception, "stderr", ""))

    def test_unsafe_parent_is_rejected_and_not_silently_deleted(self) -> None:
        directory = self.run_dir("unsafe-parent")
        directory.chmod(0o755)
        path = directory / "codex-proxy.json"
        value = self.codex_value()
        self.write_private(path, value)
        with self.assertRaises(SystemExit) as raised:
            self.load(codex_proxy, path)
        self.assertTrue(path.exists())
        self.assertNotIn(
            str(value["upstreamKey"]), getattr(raised.exception, "stderr", ""),
        )

    def test_config_requires_exact_owner_read_write_mode(self) -> None:
        for module, filename, value in (
            (session_proxy, "session-proxy.json", self.session_value()),
            (codex_proxy, "codex-proxy.json", self.codex_value()),
        ):
            with self.subTest(module=module.__name__):
                path = self.run_dir("mode-" + module.__name__) / filename
                self.write_private(path, value)
                path.chmod(0o400)
                with self.assertRaises(SystemExit) as raised:
                    self.load(module, path)
                self.assertTrue(path.exists())
                self.assertNotIn(
                    str(value["upstreamKey"]),
                    getattr(raised.exception, "stderr", ""),
                )


if __name__ == "__main__":
    unittest.main()
