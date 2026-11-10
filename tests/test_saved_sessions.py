"""Standalone saved-settings feature equivalence and validation ownership."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest

import saved_sessions as saved


FIXTURE = json.loads((Path(__file__).parent / "fixtures/saved-sessions-v1.json").read_text())


class SavedSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.identifiers = iter(["11111111-1111-4111-8111-111111111111",
                                 "22222222-2222-4222-8222-222222222222",
                                 "33333333-3333-4333-8333-333333333333"])
        self.calls = []
        self.store = self.make_store()

    def tearDown(self):
        self.temporary.cleanup()

    def canonical(self, value, models, **kwargs):
        self.calls.append((copy.deepcopy(value), kwargs))
        request = saved._profile_request_whitelist(value)
        if not isinstance(value, dict) or request.get("modelId") not in {model["id"] for model in models}:
            raise ValueError("Fixture model is no longer available.")
        request["mode"] = "custom"
        return request

    def binding(self, payload):
        value = payload.get("evidenceBinding")
        if value is None:
            return None
        if not isinstance(value, dict) or value.get("scope") not in {"route", "engine"}:
            raise ValueError("Invalid fixture evidence binding.")
        return copy.deepcopy(value)

    def resolve(self, request, models, scope):
        self.assertIn(scope, {"route", "engine"})
        return {"backend": request["backend"], "engineChanged": False,
                "engineEvidenceTier": "cross-engine-local-benchmark",
                "engineEvidenceLabel": "Measured exact controls", "engineRationale": ["Exact native fixture"]}

    def read(self, path):
        return json.loads(path.read_text()) if path.exists() else {}

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False))

    def make_store(self, **changes):
        values = dict(profile_path=lambda: self.root / "profiles.json", set_path=lambda: self.root / "sets.json",
                      profile_lock=threading.Lock(), set_lock=threading.Lock(), read=self.read, write=self.write,
                      validate_request=self.canonical, validate_binding=self.binding, resolve_measured=self.resolve,
                      backend_labels=FIXTURE["backendLabels"], client_labels=FIXTURE["clientLabels"],
                      now=lambda: "2026-10-06T13:00:00+00:00", new_id=lambda: next(self.identifiers))
        return saved.SavedSessionStore(**{**values, **changes})

    def test_frozen_pre_extraction_crud_inventory_requests_and_documents_match(self):
        models, request, binding = [FIXTURE["model"]], FIXTURE["request"], FIXTURE["binding"]
        fixed = self.store.save_launch_profile({"name": "Fixed 雪", "request": request}, models)
        measured = self.store.save_launch_profile({"name": "Measured", "request": request,
                                                  "enginePolicy": "measured", "evidenceBinding": binding}, models)
        updated = self.store.save_launch_profile({"id": fixed["profiles"][0]["id"], "name": "Fixed updated", "request": request}, models)
        unavailable = self.store.launch_profile_inventory([])
        profile_doc = self.read(self.store.profile_path())
        sets = self.store.save_active_session_set({"name": "Workspace 雪"}, models,
                                                 lambda: (FIXTURE["activeBase"], FIXTURE["activeSurfaces"]))
        set_doc = self.read(self.store.set_path())
        requests = self.store.session_set_requests(set_doc["sets"][0], models)
        actual = {"fixed": fixed, "measured": measured, "updated": updated,
                  "profilesUnavailable": unavailable, "profileDocument": profile_doc,
                  "sets": sets, "setDocument": set_doc, "requests": requests,
                  "setsUnavailable": self.store.session_set_inventory([])}
        self.assertEqual(actual, FIXTURE["expected"])
        self.assertNotIn("SECRET", json.dumps(profile_doc))
        self.assertNotIn("TRANSCRIPT", json.dumps(set_doc))

    def test_snapshot_callback_is_data_only_and_is_not_called_for_invalid_metadata(self):
        captures = []
        def capture():
            captures.append(True)
            return FIXTURE["activeBase"], FIXTURE["activeSurfaces"]
        with self.assertRaisesRegex(ValueError, "name"):
            self.store.save_active_session_set({"name": ""}, [FIXTURE["model"]], capture)
        self.assertEqual(captures, [])
        self.store.save_active_session_set({"name": "Current workspace"}, [FIXTURE["model"]], capture)
        self.assertEqual(captures, [True])

    def test_model_unavailability_is_revalidated_on_every_inventory_and_never_cached(self):
        self.store.save_launch_profile({"name": "Settings", "request": FIXTURE["request"]}, [FIXTURE["model"]])
        before = len(self.calls)
        unavailable = self.store.launch_profile_inventory([])
        self.assertGreater(len(self.calls), before)
        self.assertFalse(unavailable["profiles"][0]["ready"])
        self.assertTrue(self.store.launch_profile_inventory([FIXTURE["model"]])["profiles"][0]["ready"])

    def test_malformed_evidence_tombstone_survives_unrelated_profile_save(self):
        self.write(self.store.profile_path(), {"version": 1, "profiles": [{
            "id": "99999999-9999-4999-8999-999999999999", "name": "Damaged reference",
            "enginePolicy": "measured", "enginePreference": "throughput", "request": FIXTURE["activeBase"],
            "evidenceBinding": {"scope": "invalid"}, "createdAt": "", "updatedAt": "", "modelName": "Exact model"}]})
        self.store.save_launch_profile({"name": "Unrelated", "request": FIXTURE["request"]}, [FIXTURE["model"]])
        record = self.store.load_launch_profiles()[1]
        self.assertTrue(record["_evidenceBindingInvalid"])
        self.assertFalse(self.store.launch_profile_inventory([FIXTURE["model"]])["profiles"][1]["ready"])

    def test_surface_cannot_replace_shared_engine_contract_and_all_controls_stay_exact(self):
        def changed(value, models, **kwargs):
            result = self.canonical(value, models, **kwargs)
            if result["client"] == "chat":
                result["output"] += 1
            return result
        self.store.validate_request = changed
        with self.assertRaisesRegex(ValueError, "shared model contract"):
            self.store.validated_session_set_record({"baseRequest": FIXTURE["activeBase"], "surfaces": FIXTURE["activeSurfaces"]}, [FIXTURE["model"]])

    def test_limits_duplicate_names_update_order_and_private_writer_return(self):
        self.store.policy = replace(saved.DEFAULT_POLICY, profile_limit=1, set_limit=1)
        first = self.store.save_launch_profile({"name": "Exact", "request": FIXTURE["request"]}, [FIXTURE["model"]])
        with self.assertRaisesRegex(ValueError, "already uses"):
            self.store.save_launch_profile({"name": "exact", "request": FIXTURE["request"]}, [FIXTURE["model"]])
        with self.assertRaisesRegex(ValueError, "at most 1"):
            self.store.save_launch_profile({"name": "Extra", "request": FIXTURE["request"]}, [FIXTURE["model"]])
        identifier = first["profiles"][0]["id"]
        updated = self.store.save_launch_profile({"id": identifier, "name": "Renamed", "request": FIXTURE["request"]}, [FIXTURE["model"]])
        self.assertEqual(updated["profiles"][0]["createdAt"], first["profiles"][0]["createdAt"])
        self.assertIsNone(self.store._write_launch_profiles_unlocked(self.store.load_launch_profiles()))
        self.assertEqual(self.store.delete_launch_profile({"id": identifier}, [FIXTURE["model"]])["profiles"], [])

    def test_surface_overflow_is_not_silently_truncated_into_a_valid_set(self):
        self.store.policy = replace(saved.DEFAULT_POLICY, surface_limit=2)
        value = {"baseRequest": FIXTURE["activeBase"], "surfaces": FIXTURE["activeSurfaces"] * 2}
        with self.assertRaisesRegex(ValueError, "at most 2"):
            self.store.validated_session_set_record(value, [FIXTURE["model"]])

    def test_all_permitted_profiles_with_worst_case_escaping_exceed_4mib_and_round_trip(self):
        store = self.make_store(read=None, write=None)
        request = copy.deepcopy(FIXTURE["activeBase"])
        request.update(client="chat", agentHost="launcher", chat={"systemPrompt": "\x01" * 32_000, "sampling": "model"})
        records = [{"id": f"{index:08x}-1111-4111-8111-111111111111", "name": f"Profile {index}",
                    "createdAt": "", "updatedAt": "", "modelName": "Exact model", "enginePolicy": "fixed",
                    "enginePreference": "throughput", "request": request} for index in range(32)]
        store._write_launch_profiles_unlocked(records)
        self.assertGreater(store.profile_path().stat().st_size, 4 * 1024 * 1024)
        loaded = store.load_launch_profiles()
        self.assertEqual(loaded, records)
        self.assertEqual(store.profile_path().stat().st_mode & 0o777, 0o600)

    def test_all_permitted_sets_and_surfaces_with_maximum_system_prompts_round_trip(self):
        store = self.make_store(read=None, write=None)
        request = copy.deepcopy(FIXTURE["activeBase"])
        request.update(client="chat", agentHost="launcher", chat={"systemPrompt": "A" * 32_000, "sampling": "model"})
        surface = saved._session_set_surface_from_request(request)
        records = [{"id": f"{index:08x}-2222-4222-8222-222222222222", "name": f"Set {index}",
                    "createdAt": "", "updatedAt": "", "modelName": "Exact model",
                    "baseRequest": request, "surfaces": [surface] * 11} for index in range(16)]
        store._write_session_sets_unlocked(records)
        self.assertGreater(store.set_path().stat().st_size, 4 * 1024 * 1024)
        self.assertEqual(store.load_session_sets(), records)
        self.assertGreaterEqual(store.policy.store_bytes("sets"), 16 * 12 * 32_000 * 6)
        self.assertEqual(store.set_path().stat().st_mode & 0o777, 0o600)

    def test_historical_large_metadata_previously_under_4mib_is_not_silently_narrowed(self):
        store = self.make_store(read=None, write=None)
        record = copy.deepcopy(FIXTURE["expected"]["profileDocument"]["profiles"][0])
        record["modelName"] = "雪" * 300_000
        store._write_launch_profiles_unlocked([record])
        self.assertLess(store.profile_path().stat().st_size, 4 * 1024 * 1024)
        self.assertEqual(store.load_launch_profiles()[0]["modelName"], "雪" * 240)

    def test_corruption_unknown_version_and_record_count_preserve_file_and_stop_mutation(self):
        store = self.make_store(read=None, write=None)
        path = store.profile_path()
        for original in (b'{"profiles":[', b'{"version":2,"profiles":[]}',
                         json.dumps({"version": 1, "profiles": [{}] * 33}).encode()):
            path.write_bytes(original)
            with self.subTest(original=original[:50]), self.assertRaises(saved.SavedSettingsReadError):
                store.save_launch_profile({"name": "Must not overwrite", "request": FIXTURE["request"]}, [FIXTURE["model"]])
            self.assertEqual(path.read_bytes(), original)

    def test_individual_byte_bound_prevents_successful_write_followed_by_unreadable_record(self):
        store = self.make_store(read=None, write=None, policy=replace(saved.DEFAULT_POLICY,
                                profile_limit=2, max_system_prompt=8, metadata_bytes_per_record=64,
                                format_bytes_per_record=64))
        path = store.profile_path()
        path.write_text("Preserve original")
        # UTF-8 bytes exceed the per-record ceiling while Unicode character
        # count remains inside it, and aggregate two-record budget would fit.
        with self.assertRaises(saved.SavedSettingsReadError):
            store._write_launch_profiles_unlocked([{"name": "🙂" * 70}])
        self.assertEqual(path.read_text(), "Preserve original")

    def test_decoded_structure_and_file_identity_checks_preserve_original(self):
        from unittest.mock import patch
        store = self.make_store(read=None, write=None)
        path = store.profile_path()
        original = json.dumps({"version": 1, "profiles": [{"request": {"unknown": [0] * 3000}}]}).encode()
        path.write_bytes(original)
        with self.assertRaises(saved.SavedSettingsReadError):
            store.load_launch_profiles()
        self.assertEqual(path.read_bytes(), original)
        path.write_text('{"version":1,"profiles":[]}')
        before = path.read_bytes()
        real = Path.stat
        def changed(target, *args, **kwargs):
            result = real(target, *args, **kwargs)
            if target == path:
                values = list(result)
                values[1] += 1
                return type(result)(values)
            return result
        with patch.object(Path, "stat", changed), self.assertRaises(saved.SavedSettingsReadError):
            store.load_launch_profiles()
        self.assertEqual(path.read_bytes(), before)

    def test_writer_rejects_unreadable_versions_and_root_metadata_before_replacement(self):
        path = self.store.profile_path()
        original = b'{"version":1,"profiles":[]}'
        invalid = [{"profiles": []}, {"version": True, "profiles": []}, {"version": 2, "profiles": []},
                   {"version": 1, "profiles": [], "extra": "unknown root field"},
                   {"version": 1, "profiles": [], "updatedAt": "x" * 16385},
                   {"version": 1, "profiles": [], "updatedAt": {"wrong": "shape"}}]
        for value in invalid:
            path.write_bytes(original)
            with self.subTest(value=str(value)[:60]), self.assertRaises(saved.SavedSettingsReadError):
                saved.write_saved_document(path, value, "profiles", saved.DEFAULT_POLICY)
            self.assertEqual(path.read_bytes(), original)
        saved.write_saved_document(path, {"version": 1, "profiles": []}, "profiles", saved.DEFAULT_POLICY)
        self.assertEqual(saved.read_saved_document(path, "profiles", saved.DEFAULT_POLICY), {"version": 1, "profiles": []})


if __name__ == "__main__":
    unittest.main()
