"""Exact installed/kernel/map proofs using synthetic identities; never signal."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import launcher_shutdown
import retitled_servers as servers


class RetitledServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="retitled-server-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.env = self.root / "omlx-environment"
        self.binary = self.env / "bin/omlx"
        self.binary.parent.mkdir(parents=True)
        self.binary.write_text("#!/usr/bin/python3\nfrom omlx.cli import main\n")
        self.binary.chmod(0o755)
        self.python = self.root / "python/bin/python3.11"
        self.python.parent.mkdir(parents=True)
        self.python.write_bytes(b"\xcf\xfa\xed\xfe synthetic interpreter")
        self.python.chmod(0o755)
        self.framework = self.root / "python/Resources/Python.app/Contents/MacOS/Python"
        self.framework.parent.mkdir(parents=True)
        self.framework.write_bytes(b"\xcf\xfa\xed\xfe synthetic framework interpreter")
        self.framework.chmod(0o755)
        for name in ("python", "python3", "python3.11"):
            (self.env / "bin" / name).symlink_to(self.python)
        self.site = self.env / "lib/python3.11/site-packages"
        version = self.site / "omlx/_version.py"
        version.parent.mkdir(parents=True)
        version.write_text('__version__ = "0.5.7"\n')
        for name in ("setproctitle/_setproctitle.cpython-311-darwin.so", "mlx/core.cpython-311-darwin.so", "mlx/lib/libmlx.dylib"):
            path = self.site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic mapped library"); path.chmod(0o755)
        self.environment = servers.inspect_omlx_environment(str(self.binary))
        self.assertIsNotNone(self.environment)
        self.mapped = {(item.path, item.device, item.inode) for item in self.environment.modules}
        self.process = launcher_shutdown.LocalProcess(os.getuid(), 7182, 1, "Tue Oct 6 20:00:00 2026", "omlx-server")
        self.kernel = servers.KernelIdentity(os.getuid(), self.process.pid, 1791316800, 33, str(self.framework))
        self.snapshot = {self.process.pid: self.process}
        self.native = mock.Mock(side_effect=lambda _pid: self.kernel)
        self.maps = mock.Mock(side_effect=lambda _pid: set(self.mapped))
        self.kill = mock.patch.object(servers.os, "kill")
        self.kill_mock = self.kill.start(); self.addCleanup(self.kill.stop)

    def identify(self, binaries=None, processes=None, snapshot=None):
        result = servers.identify_retitled_servers(processes=processes if processes is not None else dict(self.snapshot),
            binaries=binaries if binaries is not None else {"omlx": str(self.binary)},
            process_snapshot=snapshot or (lambda: dict(self.snapshot)),
            native_reader=self.native, mapped_reader=self.maps)
        self.kill_mock.assert_not_called()
        return result

    def test_manual_server_title_gap_is_closed_by_independent_proof(self):
        self.assertIsNone(launcher_shutdown.process_label(self.process, {"omlx": str(self.binary)}, self.root))
        result = self.identify()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["_processReceipts"], {7182: self.process})
        self.assertEqual(result["servers"][0]["source"], "installed-oMLX-mapped-environment")
        self.assertTrue(result["_nativeReceipts"][7182].revalidate(self.native))

    def test_shared_interpreter_does_not_identify_an_unrelated_python_job(self):
        unrelated = replace(self.process, command="python3 project_analysis.py")
        result = self.identify(processes={7182: unrelated})
        self.assertEqual(result["servers"], [])
        self.assertEqual(result["errors"], [])
        self.maps.assert_not_called()

    def test_title_alone_without_installed_environment_never_issues_receipt(self):
        result = self.identify(binaries={})
        self.assertEqual(result["_processReceipts"], {})
        self.assertTrue(result["errors"])

    def test_same_environment_generic_mlx_without_setproctitle_is_not_enough(self):
        self.mapped = {item for item in self.mapped if "/setproctitle/" not in item[0]}
        result = self.identify()
        self.assertEqual(result["servers"], [])
        self.assertTrue(result["errors"])

    def test_partial_mixed_or_different_inode_maps_are_not_enough(self):
        original = set(self.mapped)
        variants = (set(), {next(iter(original))},
                    {(str(self.root / "other-environment" / Path(path).name), device, inode) for path, device, inode in original},
                    {(path, device, inode + 1) for path, device, inode in original})
        for mapped in variants:
            with self.subTest(mapped=mapped):
                self.mapped = mapped
                self.assertEqual(self.identify()["servers"], [])

    def test_wrong_interpreter_or_foreign_uid_is_rejected(self):
        original = self.kernel
        for kernel in (replace(original, executable="/unrelated/Python"), replace(original, uid=os.getuid() + 1)):
            with self.subTest(kernel=kernel):
                self.kernel = kernel
                self.assertEqual(self.identify()["servers"], [])
        self.kernel = original

    def test_foreign_process_and_current_caller_are_never_candidates(self):
        foreign = replace(self.process, uid=os.getuid() + 1)
        caller = replace(self.process, pid=os.getpid())
        self.assertEqual(self.identify(processes={foreign.pid: foreign, caller.pid: caller})["servers"], [])
        self.native.assert_not_called()

    def test_microsecond_birth_change_during_proof_is_rejected(self):
        self.native.side_effect = [self.kernel, replace(self.kernel, start_microseconds=34)]
        result = self.identify()
        self.assertEqual(result["servers"], [])
        self.assertTrue(result["errors"])

    def test_ps_birth_change_during_proof_is_rejected(self):
        result = self.identify(snapshot=lambda: {7182: replace(self.process, started="another process birth")})
        self.assertEqual(result["servers"], [])
        self.assertTrue(result["errors"])

    def test_mapped_file_replacement_during_proof_is_rejected(self):
        original = self.maps.side_effect
        def replace_file(pid):
            path = Path(self.environment.modules[0].path)
            path.rename(path.with_suffix(".old"))
            path.write_bytes(b"new unmapped file"); path.chmod(0o755)
            return original(pid)
        self.maps.side_effect = replace_file
        result = self.identify()
        self.assertEqual(result["servers"], [])
        self.assertTrue(result["errors"])

    def test_fast_revalidation_detects_pid_reuse_same_ps_second(self):
        receipt = self.identify()["_nativeReceipts"][7182]
        self.kernel = replace(self.kernel, start_microseconds=999)
        self.assertFalse(receipt.revalidate(self.native))

    def test_fast_revalidation_detects_exec_image_or_file_change(self):
        receipt = self.identify()["_nativeReceipts"][7182]
        original = self.kernel
        self.kernel = replace(original, executable="/different/Python")
        self.assertFalse(receipt.revalidate(self.native))
        self.kernel = original
        self.framework.write_bytes(b"changed interpreter")
        self.assertFalse(receipt.revalidate(self.native))

    def test_public_summary_does_not_expose_command_or_package_paths(self):
        result = self.identify()
        self.assertNotIn("command", result["servers"][0])
        self.assertNotIn("executable", result["servers"][0])
        self.assertNotIn("environment", result["servers"][0])

    def test_dedicated_native_server_identity_survives_arbitrary_title(self):
        binary = self.root / "llama-server"
        binary.write_bytes(b"\xcf\xfa\xed\xfe synthetic server"); binary.chmod(0o755)
        self.process = replace(self.process, command="a retitled native server")
        self.snapshot = {7182: self.process}
        self.kernel = replace(self.kernel, executable=str(binary))
        result = self.identify(binaries={"llamacpp": str(binary)})
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["servers"][0]["engine"], "llamacpp")
        self.assertEqual(result["servers"][0]["source"], "installed-dedicated-native-server")
        self.maps.assert_not_called()

    def test_native_identity_cannot_match_script_or_generic_cli(self):
        for name, content in (("llama-server", b"#!/usr/bin/python3\n"), ("llama-cli", b"\xcf\xfa\xed\xfe")):
            with self.subTest(name=name):
                binary = self.root / name
                binary.write_bytes(content); binary.chmod(0o755)
                self.process = replace(self.process, command="generic native tool")
                self.snapshot = {7182: self.process}
                self.kernel = replace(self.kernel, executable=str(binary))
                self.assertEqual(self.identify(binaries={"llamacpp": str(binary)})["servers"], [])

    def test_unsafe_known_native_executable_is_reported_honestly(self):
        binary = self.root / "llama-server"
        binary.write_bytes(b"\xcf\xfa\xed\xfe synthetic server"); binary.chmod(0o777)
        self.process = replace(self.process, command="retitled native process")
        self.snapshot = {7182: self.process}
        self.kernel = replace(self.kernel, executable=str(binary))
        result = self.identify(binaries={"llamacpp": str(binary)})
        self.assertEqual(result["servers"], [])
        self.assertTrue(result["errors"])

    def test_busy_server_needs_no_http_or_listener_corroboration(self):
        # Independent native/install/map proof works during busy/disabled or
        # authenticated HTTP, so the explicit Quit scope is not narrowed.
        result = self.identify()
        self.assertEqual(result["servers"][0]["engine"], "omlx")
        self.assertEqual(result["errors"], [])

    def test_environment_rejects_unknown_entry_point_and_writable_modules(self):
        self.binary.write_text("#!/usr/bin/python3\nprint('unrelated')\n")
        self.assertIsNone(servers.inspect_omlx_environment(str(self.binary)))
        self.binary.write_text("from omlx.cli import main\n")
        Path(self.environment.modules[0].path).chmod(0o777)
        self.assertIsNone(servers.inspect_omlx_environment(str(self.binary)))

    def test_global_or_other_environment_library_symlink_cannot_form_local_proof(self):
        module = Path(self.environment.modules[0].path)
        outside = self.root / "global-setproctitle.so"
        module.rename(outside)
        module.symlink_to(outside)
        self.assertIsNone(servers.inspect_omlx_environment(str(self.binary)))

    def test_mapped_machine_fields_ignore_regular_open_files_and_preserve_exact_inode(self):
        data = (b"p7182\0\nftxt\0tREG\0D0x1000011\0i123\0n/exact/module.so\0\n"
                b"f4\0tREG\0D0x1000011\0i999\0n/unrelated/open.so\0\n")
        response = mock.Mock(returncode=0, stdout=data)
        with mock.patch.object(servers.subprocess, "run", return_value=response):
            self.assertEqual(servers.native_mapped_files(7182), {("/exact/module.so", 0x1000011, 123)})
        with mock.patch.object(servers.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=data.replace(b"p7182", b"p7183"))):
            self.assertIsNone(servers.native_mapped_files(7182))

    def test_native_abi_and_unavailable_platform_fail_closed(self):
        self.assertEqual(servers.ctypes.sizeof(servers._BSDInfo), 136)
        self.assertEqual(servers._BSDInfo.start_seconds.offset, 120)
        with mock.patch.object(servers.sys, "platform", "linux"):
            self.assertIsNone(servers.native_process_identity(7182))
        for pid in (True, 0, 1, -1, "7182"):
            self.assertIsNone(servers.native_process_identity(pid))


if __name__ == "__main__":
    unittest.main()
