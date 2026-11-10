"""Measurement storage failures stay visible through actual controller facades."""
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import launcher
import measurement_store
from test_measurement_store import record


class MeasurementStorageAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix="measurement-api-")
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        patcher=mock.patch.object(launcher,"STATE_DIR",self.root)
        patcher.start();self.addCleanup(patcher.stop)

    def handler(self,path,payload=None):
        data=json.dumps(payload or {}).encode()
        handler=object.__new__(launcher.Handler)
        handler.path=path
        handler.headers={"Host":"127.0.0.1","X-Launcher-Token":"generated-token",
            "Origin":"http://127.0.0.1:1234","Content-Length":str(len(data))}
        handler.server=SimpleNamespace(csrf_token="generated-token")
        handler.rfile=io.BytesIO(data);handler.wfile=io.BytesIO()
        handler.send_error=mock.Mock();replies=[]
        handler.json_response=lambda value,status=200:replies.append((value,int(status)))
        return handler,replies

    def test_all_public_measurement_facades_keep_current_retention_and_none_writer_returns(self):
        for kind,save,load,path in (
            ("benchmark",launcher.save_benchmark_record,launcher.load_benchmark_records,launcher.benchmark_store_path),
            ("ane",launcher.save_ane_tuning_record,launcher.load_ane_tuning_records,launcher.ane_tuning_store_path),
            ("promotion",launcher.save_runtime_promotion_record,launcher.load_runtime_promotion_records,launcher.runtime_promotion_store_path)):
            with self.subTest(kind=kind):
                self.assertIsNone(save(record(1,kind)))
                self.assertEqual(load(),[record(1,kind)])
                self.assertEqual(path().stat().st_mode & 0o777,0o600)
                self.assertEqual(path().with_name(path().name+".lock").stat().st_mode & 0o777,0o600)

    def test_exact_retention_callback_stays_late_bound_and_store_objects_hold_no_controller_namespace(self):
        with mock.patch.object(launcher,"benchmark_record_identity",side_effect=lambda row:(row["modelFingerprint"],)) as identify:
            launcher.save_benchmark_records([record(1),record(2)])
            self.assertEqual(identify.call_count,2)
        store=launcher._measurement_store("benchmark")
        self.assertIsInstance(store,measurement_store.MeasurementStore)
        self.assertNotIn("launcher",store.__dict__)

    def test_corrupt_benchmark_history_returns_a_bounded_storage_error_and_keeps_bytes(self):
        original=b'{"version":1,"PRIVATE":"do not expose",'
        launcher.benchmark_store_path().write_bytes(original)
        handler,replies=self.handler("/api/benchmark/history",{})
        with mock.patch.object(launcher,"controller_source_is_current",return_value=True), \
                mock.patch.object(launcher.CONTROLLER_QUITTING,"is_set",return_value=False), \
                mock.patch.object(launcher,"presentation_models",return_value=[]), \
                mock.patch.object(launcher,"benchmark_history_request",side_effect=lambda *_args:launcher.load_benchmark_records()):
            launcher.Handler.do_POST(handler)
        self.assertEqual(len(replies),1)
        value,status=replies[0]
        self.assertEqual(status,503)
        self.assertTrue(value["storageError"])
        self.assertFalse(value["ok"])
        self.assertNotIn("PRIVATE",value["error"])
        self.assertLessEqual(len(value["error"]),600)
        self.assertEqual(launcher.benchmark_store_path().read_bytes(),original)
        handler.send_error.assert_not_called()

    def test_missing_stores_remain_read_only_and_unknown_versions_never_reset_history(self):
        for load,path in ((launcher.load_benchmark_records,launcher.benchmark_store_path),
                         (launcher.load_ane_tuning_records,launcher.ane_tuning_store_path),
                         (launcher.load_runtime_promotion_records,launcher.runtime_promotion_store_path)):
            with self.subTest(path=path.__name__):
                self.assertEqual(load(),[]);self.assertFalse(path().exists())
                original=b'{"version":999,"records":[]}'
                path().write_bytes(original)
                with self.assertRaises(measurement_store.MeasurementStoreError):load()
                self.assertEqual(path().read_bytes(),original)


if __name__=="__main__":unittest.main()
