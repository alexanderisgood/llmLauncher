"""Bounded complete measurement persistence; generated records, no AI engines."""
import copy
import fcntl
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import chat_store_io
import measurement_store as storage


def record(index, kind="benchmark", **extra):
    value={"id":str(index),"createdAt":f"2026-10-06T12:00:{index % 60:02d}Z","scope":"local",
        "backend":"omlx","modelFingerprint":f"model-{index % 3}","runtimeVersion":"fixture",
        "hardwareFingerprint":"fixture-mac","winner":"ar","comparedModes":["ar"],
        "sequenceLength":index % 3,"recommendation":{},"status":"completed",
        "contractId":"fixture-contract","planId":"fixture-plan","selected":{},"candidate":{},
        "executionOrder":["selected","candidate"],"qualityMatched":True,"resourceComparable":True,
        "canPromote":False,"measurements":{}}
    value.update(extra)
    return value


def identity(value):
    return (value.get("modelFingerprint"),value.get("runtimeVersion"),value.get("hardwareFingerprint"))


class MeasurementStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix="measurement-store-")
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)

    def store(self,kind="benchmark",**limits):
        policy=storage.MeasurementPolicy(kind,1,192,12,frozenset({"kolibri"}),**limits)
        return storage.MeasurementStore(policy,lambda:self.root/(kind+".json"),route_identity=identity)

    def test_full_retention_and_json_output_match_frozen_legacy_for_all_three_kinds(self):
        fixture=Path(__file__).with_name("fixtures")/"measurement_store_legacy.py"
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(),
            json.loads(fixture.with_suffix(".json").read_text())["sourceSha256"])
        for kind in ("benchmark","ane","promotion"):
            with self.subTest(kind=kind):
                legacy=self.root/(kind+"-legacy"); legacy.mkdir()
                def read(path):
                    return json.loads(path.read_text()) if path.exists() else {}
                def write(path,value):
                    path.write_text(json.dumps(value))
                namespace={"Path":Path,"Any":object,"copy":copy,"re":__import__("re"),"threading":threading,
                    "STATE_DIR":legacy,"BENCHMARK_STORE_VERSION":1,"BENCHMARK_MAX_RECORDS":192,
                    "BENCHMARK_MAX_HISTORY_PER_ROUTE":12,"SSD_STREAMING_BACKENDS":("kolibri",),
                    "benchmark_record_identity":identity,"read_json":read,"atomic_json":write,
                    "ANE_TUNER_STORE_VERSION":1,"ANE_TUNER_MAX_RECORDS":192,
                    "RUNTIME_PROMOTION_SCHEMA_VERSION":1,"RUNTIME_PROMOTION_MAX_RECORDS":192,
                    "RUNTIME_PROMOTION_STORE":"promotion.json","RUNTIME_PROMOTION_LOCK":threading.Lock()}
                exec(compile(fixture.read_text(),str(fixture),"exec"),namespace)
                store=self.store(kind)
                for start in (0,30,60):
                    rows=[record(i,kind,shootoutId=("shared" if i % 7 == 0 else "")) for i in range(start,start+30)]
                    if kind=="benchmark":namespace["save_benchmark_records"](rows);store.save(rows)
                    else:
                        legacy_save=namespace["save_ane_tuning_record" if kind=="ane" else "save_runtime_promotion_record"]
                        for row in rows:legacy_save(row);store.save([row])
                expected=namespace[{"benchmark":"load_benchmark_records","ane":"load_ane_tuning_records","promotion":"load_runtime_promotion_records"}[kind]]()
                self.assertEqual(store.load(),expected)

    def test_large_valid_history_roundtrips_instead_of_becoming_an_empty_store(self):
        store=self.store()
        rows=[record(i,notes="x"*800_000) for i in range(6)]
        store.save(rows)
        self.assertGreater(store.path().stat().st_size,4*1024*1024)
        self.assertEqual(store.load(),rows)
        store.save([record(7,notes="another measured route")])
        self.assertEqual(len(store.load()),7)
        self.assertEqual(os.stat(store.path()).st_mode & 0o777,0o600)

    def test_bad_existing_documents_are_preserved_and_cannot_be_overwritten_by_append(self):
        for raw in (b'{',b'{"version":2,"records":[]}',b'{"version":true,"records":[]}',
                    b'{"version":1,"records":{}}',b'{"version":1,"records":[null]}',
                    b'{"version":1,"version":1,"records":[]}',
                    b'{"version":1,"records":[{"id":"first","id":"second"}]}',
                    b'{"version":1,"records":[{"speed":NaN}]}'):
            with self.subTest(raw=raw):
                store=self.store();store.path().write_bytes(raw)
                with self.assertRaises(storage.MeasurementStoreError):store.load()
                with self.assertRaises(storage.MeasurementStoreError):store.save([record(1)])
                self.assertEqual(store.path().read_bytes(),raw)

    def test_file_and_record_quota_failure_leave_the_previous_measurements_readable(self):
        store=self.store(maximum_bytes=4000,maximum_record_bytes=2500)
        store.save([record(1)])
        before=store.path().read_bytes()
        with self.assertRaises(storage.MeasurementStoreError):store.save([record(2,notes="x"*3000)])
        self.assertEqual(store.path().read_bytes(),before)
        with self.assertRaises(storage.MeasurementStoreError):store.save([record(i,notes="x"*600) for i in range(2,6)])
        self.assertEqual(store.path().read_bytes(),before)
        self.assertEqual(store.load(),[record(1)])

    def test_cached_decode_is_detached_and_external_edits_are_observed_immediately(self):
        store=self.store();store.save([record(1)])
        with mock.patch.object(chat_store_io,"read_document",wraps=chat_store_io.read_document) as read:
            first=store.load();first[0]["winner"]="forged"
            self.assertEqual(store.load()[0]["winner"],"ar")
            self.assertEqual(read.call_count,1)
            store.path().write_text(json.dumps({"version":1,"records":[record(2)]}))
            self.assertEqual(store.load(),[record(2)])
            self.assertEqual(read.call_count,2)

    def test_overlapping_threads_keep_every_distinct_measurement(self):
        store=self.store();errors=[];barrier=threading.Barrier(8)
        def append(i):
            try:barrier.wait(2);store.save([record(i,modelFingerprint=f"distinct-{i}")])
            except Exception as error:errors.append(error)
        workers=[threading.Thread(target=append,args=(i,)) for i in range(8)]
        for worker in workers:worker.start()
        for worker in workers:worker.join(5)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors,[])
        self.assertEqual({item["id"] for item in store.load()},set(map(str,range(8))))

    def test_overlapping_processes_use_the_same_private_append_lock(self):
        code="""import pathlib,sys
import measurement_store as s
root=pathlib.Path(sys.argv[1]); i=sys.argv[2]
store=s.MeasurementStore(s.MeasurementPolicy('ane',1,32),lambda:root/'ane.json')
store.save([{'id':i,'createdAt':'fixture','scope':'local','modelFingerprint':i,'runtimeVersion':'fixture','hardwareFingerprint':'fixture','sequenceLength':1,'recommendation':{},'status':'completed'}])
"""
        workers=[subprocess.Popen([sys.executable,"-c",code,str(self.root),str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for i in range(6)]
        try:
            for worker in workers:
                out,err=worker.communicate(timeout=5)
                self.assertEqual(worker.returncode,0,err.decode()[:500])
        finally:
            for worker in workers:
                if worker.poll() is None:worker.kill()
                worker.wait()
        self.assertEqual({item["id"] for item in self.store("ane").load()},set(map(str,range(6))))

    def test_a_busy_external_append_lock_times_out_without_losing_or_overwriting_data(self):
        store=self.store(append_lock_timeout_seconds=.05);store.save([record(1)])
        before=store.path().read_bytes()
        with open(store.path().with_name(store.path().name+".lock"),"r+") as handle:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(storage.MeasurementStoreError,"still saving"):
                store.save([record(2)])
        self.assertEqual(store.path().read_bytes(),before)
        store.save([record(2)])
        self.assertEqual(len(store.load()),2)

    def test_nonfinite_new_values_fail_before_creating_a_store(self):
        store=self.store()
        with self.assertRaisesRegex(storage.MeasurementStoreError,"non-finite"):
            store.save([record(1,medianSpeed=float("inf"))])
        self.assertFalse(store.path().exists())

    def test_external_edit_before_replace_is_preserved(self):
        store=self.store();store.save([record(1)])
        original=chat_store_io.write_document
        replacement={"version":1,"records":[record(3)]}
        def interrupted(path,value,**kwargs):
            path.write_text(json.dumps(replacement))
            return original(path,value,**kwargs)
        with mock.patch.object(chat_store_io,"write_document",side_effect=interrupted):
            with self.assertRaisesRegex(storage.MeasurementStoreError,"changed before commit"):
                store.save([record(2)])
        self.assertEqual(store.load(),[record(3)])
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_symlink_and_foreign_write_permissions_cannot_redirect_or_replace_measurements(self):
        store=self.store();target=self.root/"unrelated.json";target.write_text('{"version":1,"records":[]}')
        store.path().symlink_to(target)
        with self.assertRaises(storage.MeasurementStoreError):store.load()
        with self.assertRaises(storage.MeasurementStoreError):store.save([record(1)])
        self.assertTrue(store.path().is_symlink());self.assertEqual(target.read_text(),'{"version":1,"records":[]}')
        store.path().unlink();store.path().write_text('{"version":1,"records":[]}');store.path().chmod(0o666)
        with self.assertRaises(storage.MeasurementStoreError):store.load()

    def test_ssd_identity_validation_keeps_exact_legacy_rejections(self):
        store=self.store()
        for row in (record(1,backend="kolibri"),record(1,ssdStreaming=True,ssdComparisonIdentity="a"*64)):
            with self.assertRaises(ValueError):store.save([row])
        self.assertFalse(store.path().exists())
        row=record(2,backend="kolibri",ssdStreaming=True,ssdComparisonIdentity="a"*64)
        store.save([row]);self.assertEqual(store.load(),[row])

    def test_unknown_root_metadata_is_retained_and_only_explicit_store_versions_are_supported(self):
        store=self.store();store.path().write_text(json.dumps({"version":1,"records":[record(1)],"annotation":{"source":"fixture"}}))
        store.save([record(2)])
        self.assertEqual(json.loads(store.path().read_text())["annotation"],{"source":"fixture"})
        with self.assertRaises(ValueError):replace(store.policy,maximum_records=True)

    def test_compact_metadata_stays_readable_after_an_append(self):
        store=self.store("ane")
        annotation=[0]*4000
        store.path().write_text(json.dumps({"version":1,"records":[],"annotation":annotation},separators=(",",":")))
        self.assertEqual(store.load(),[])
        store.save([record(1,"ane")])
        self.assertEqual(store.load(),[record(1,"ane")])
        self.assertEqual(json.loads(store.path().read_text())["annotation"],annotation)

    def test_exact_root_value_and_key_byte_limits_roundtrip_without_formatting_overhead(self):
        store=self.store("ane")
        key="k"*(16*1024-2)
        annotation="x"*(16*1024-2)
        store.path().write_text(json.dumps({"version":1,"records":[],key:annotation},separators=(",",":")))
        self.assertEqual(store.load(),[])
        store.save([record(1,"ane")])
        self.assertEqual(store.load(),[record(1,"ane")])
        self.assertEqual(json.loads(store.path().read_text())[key],annotation)

    def test_nonfinite_root_metadata_is_preserved_as_an_explicit_read_error(self):
        store=self.store("ane");raw=b'{"version":1,"records":[],"annotation":NaN}'
        store.path().write_bytes(raw)
        with self.assertRaisesRegex(storage.MeasurementStoreError,"non-finite"):store.load()
        with self.assertRaises(storage.MeasurementStoreError):store.save([record(1,"ane")])
        self.assertEqual(store.path().read_bytes(),raw)

    def test_hardlinked_append_lock_cannot_change_an_unrelated_files_permissions(self):
        store=self.store("ane")
        unrelated=self.root/"unrelated.txt";unrelated.write_text("unrelated contents");unrelated.chmod(0o644)
        os.link(unrelated,store.path().with_name(store.path().name+".lock"))
        with self.assertRaisesRegex(storage.MeasurementStoreError,"owner-controlled"):
            store.save([record(1,"ane")])
        self.assertEqual(unrelated.stat().st_mode & 0o777,0o644)
        self.assertEqual(unrelated.read_text(),"unrelated contents")
        self.assertFalse(store.path().exists())


if __name__=="__main__":unittest.main()
