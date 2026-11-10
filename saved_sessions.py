"""Saved launches and Session Sets: private settings-only persistence and CRUD.

Runtime/model/capacity/sampling validation remains with the caller. This store
receives exact validation and measured-resolution callbacks, never a controller
or its global namespace. Every inventory/mutation validates against current
models; persisted records are never cached as launch-admission truth.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, ContextManager, Protocol
from types import MappingProxyType
import uuid

from chat_store_io import StoreReadError, read_document, write_document


PROFILE_OPTION_KEYS = frozenset({
    "acceleration", "depth", "profile", "kv", "fan", "burst", "mtplxOperatorRoute", "memoryGB", "memoryMode", "expertResidentPercent", "omlxMemoryGB",
    "dflashVerify", "dflashDraftQuant", "anePrefill", "memoryGuard", "gpu", "parallel", "mtpMinTokens", "mtpMinContinueProbability",
    "maxBatchSize", "expertCacheSize", "prefixCacheEntries", "prefillSize", "nativeExpertTopK", "promptCacheMode", "queueLimit",
})
PROFILE_CHAT_KEYS = frozenset({
    "systemPrompt", "sampling", "temperature", "topP", "topK", "presencePenalty", "frequencyPenalty", "repetitionPenalty", "seed",
})
SESSION_SET_ENGINE_KEYS = frozenset({"backend", "modelId", "context", "output", "reasoning", "options"})


@dataclass(frozen=True)
class SavedSessionPolicy:
    profile_version: int = 1
    profile_limit: int = 32
    profile_name_max: int = 60
    set_version: int = 1
    set_limit: int = 16
    set_name_max: int = 60
    surface_limit: int = 12
    preferences: frozenset[str] = frozenset({"throughput", "fastest", "responsive", "memory", "thermal"})
    option_keys: frozenset[str] = PROFILE_OPTION_KEYS
    chat_keys: frozenset[str] = PROFILE_CHAT_KEYS
    generation_keys: frozenset[str] = frozenset({"sampling", "temperature", "topP", "topK", "presencePenalty", "frequencyPenalty", "repetitionPenalty", "seed"})
    shared_engine_keys: frozenset[str] = SESSION_SET_ENGINE_KEYS
    max_system_prompt: int = 32_000
    # Preserve every settings record previously readable under the controller's
    # 4MiB metadata ceiling, including long historical labels/identifiers. Add
    # the separately permitted system-prompt budget, rather than guessing a
    # smaller bound for fields whose source validators impose no length limit.
    metadata_bytes_per_record: int = 4 * 1024 * 1024
    format_bytes_per_record: int = 64 * 1024

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if name in {"preferences", "option_keys", "chat_keys", "generation_keys", "shared_engine_keys"}:
                if not isinstance(value, frozenset) or any(not isinstance(item, str) or not item for item in value):
                    raise ValueError(f"Saved settings policy {name} must contain names")
            elif type(value) is not int or value < 1:
                raise ValueError(f"Saved settings policy {name} must be a positive integer or immutable names")

    @property
    def profile_record_bytes(self) -> int:
        return self.max_system_prompt * 6 + self.metadata_bytes_per_record + self.format_bytes_per_record

    @property
    def set_record_bytes(self) -> int:
        return self.max_system_prompt * 6 * self.surface_limit + self.metadata_bytes_per_record + self.format_bytes_per_record

    def store_bytes(self, collection: str) -> int:
        self.record_limit(collection)
        # JSON can escape an allowed character into six ASCII bytes. Bounds
        # cover ALL permitted records, rather than generic 4MiB JSON metadata.
        return (self.profile_record_bytes * self.profile_limit if collection == "profiles"
                else self.set_record_bytes * self.set_limit) + 16 * 1024

    def record_bytes(self, collection: str) -> int:
        self.record_limit(collection)
        return self.profile_record_bytes if collection == "profiles" else self.set_record_bytes

    def record_limit(self, collection: str) -> int:
        if collection not in ("profiles", "sets"):
            raise ValueError("Choose a saved profiles or Session Sets collection")
        return self.profile_limit if collection == "profiles" else self.set_limit


DEFAULT_POLICY = SavedSessionPolicy()


class SavedSettingsReadError(StoreReadError):
    """A saved settings file cannot be read/written safely; preserve it."""


def _record_bounds(record: dict[str, Any], collection: str, policy: SavedSessionPolicy) -> None:
    surfaces = 1 if collection == "profiles" else policy.surface_limit
    maximum_nodes = 2048 * surfaces
    maximum_characters = policy.max_system_prompt * surfaces + policy.metadata_bytes_per_record
    nodes, characters = 0, 0
    pending = [(record, 0)]
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if nodes > maximum_nodes or depth > 12:
            raise SavedSettingsReadError("Saved settings contain excessive structured data; the existing file was kept.")
        if isinstance(value, str):
            characters += len(value)
        elif isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise SavedSettingsReadError("Saved settings contain invalid object keys; the existing file was kept.")
            characters += sum(len(key) for key in value)
            if len(value) > maximum_nodes - nodes - len(pending):
                raise SavedSettingsReadError("Saved settings contain excessive structured data; the existing file was kept.")
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            if len(value) > maximum_nodes - nodes - len(pending):
                raise SavedSettingsReadError("Saved settings contain excessive structured data; the existing file was kept.")
            pending.extend((item, depth + 1) for item in value)
        if characters > maximum_characters:
            raise SavedSettingsReadError("Saved settings exceed their supported record size; the existing file was kept.")


def read_saved_document(path: Path, collection: str, policy: SavedSessionPolicy) -> dict[str, Any]:
    try:
        value = read_document(
            path, collection_key=collection, maximum_bytes=policy.store_bytes(collection),
            maximum_record_bytes=policy.record_bytes(collection), maximum_records=policy.record_limit(collection),
            maximum_structural_tokens=2048 * (1 if collection == "profiles" else policy.surface_limit) * 8,
            validate_record=lambda record: _record_bounds(record, collection, policy),
        )
        expected_version = policy.profile_version if collection == "profiles" else policy.set_version
        if value and (type(value.get("version")) is not int or value["version"] != expected_version):
            raise SavedSettingsReadError("Saved settings have an unsupported storage version; the existing file was kept.")
        return value
    except StoreReadError as error:
        raise SavedSettingsReadError(str(error).replace("Saved chats", "Saved settings")) from error


def write_saved_document(path: Path, value: Any, collection: str, policy: SavedSessionPolicy) -> None:
    try:
        policy.record_limit(collection)
        expected_version = policy.profile_version if collection == "profiles" else policy.set_version
        if (not isinstance(value, dict) or type(value.get("version")) is not int
                or value["version"] != expected_version
                or not set(value).issubset({"version", "updatedAt", collection})):
            raise SavedSettingsReadError("Saved settings have an unsupported storage format; the existing file was kept.")
        if "updatedAt" in value:
            timestamp = value["updatedAt"]
            if not isinstance(timestamp, str) or len(json.dumps(timestamp, ensure_ascii=False).encode("utf-8")) > 16 * 1024:
                raise SavedSettingsReadError("Saved settings contain excessive root metadata; the existing file was kept.")
        records = value.get(collection) if isinstance(value, dict) else None
        if not isinstance(records, list) or len(records) > policy.record_limit(collection):
            raise SavedSettingsReadError("Saved settings exceed their supported record count; the existing file was kept.")
        for record in records:
            if not isinstance(record, dict):
                raise SavedSettingsReadError("Saved settings contain an invalid record; the existing file was kept.")
            _record_bounds(record, collection, policy)
            # The streaming document writer adds four spaces to every pretty
            # record line (root object + collection nesting). Count that exact
            # format without retaining an additional serialized record, so no
            # successful write can exceed the reader's per-record byte ceiling.
            record_bytes = 0
            for piece in json.JSONEncoder(indent=2, ensure_ascii=False, allow_nan=False).iterencode(record):
                record_bytes += len(piece.encode("utf-8")) + 4 * piece.count("\n")
                if record_bytes > policy.record_bytes(collection):
                    raise SavedSettingsReadError("Saved settings exceed their supported record size; the existing file was kept.")
        write_document(path, value, maximum_bytes=policy.store_bytes(collection))
    except StoreReadError as error:
        raise SavedSettingsReadError(str(error).replace("Saved chats", "Saved settings")) from error
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise SavedSettingsReadError("Saved settings could not be written safely; the existing file was kept.") from error


class RequestValidator(Protocol):
    def __call__(self, value: Any, models: list[dict[str, Any]], *,
                 preserve_comparison_controls: bool = False) -> dict[str, Any]: ...


class MeasuredResolver(Protocol):
    def __call__(self, request: dict[str, Any], models: list[dict[str, Any]], scope: str) -> dict[str, Any]: ...


def _profile_request_whitelist(value: Any, *, policy: SavedSessionPolicy = DEFAULT_POLICY) -> dict[str, Any]:
    """Strip transcripts, credentials, ports, and unknown future fields before exposure or storage."""
    if not isinstance(value, dict):
        return {}
    request = {
        key: copy.deepcopy(value[key])
        for key in (
            "backend", "client", "modelId", "project", "context", "output",
            "reasoning", "mode", "agentHost",
        )
        if key in value
    }
    raw_options = value.get("options")
    if isinstance(raw_options, dict):
        request["options"] = {
            key: copy.deepcopy(raw_options[key])
            for key in policy.option_keys if key in raw_options
        }
    raw_generation = value.get("generation")
    if isinstance(raw_generation, dict):
        request["generation"] = {
            key: copy.deepcopy(raw_generation[key])
            for key in policy.generation_keys if key in raw_generation
        }
    raw_chat = value.get("chat")
    if value.get("client") == "chat" and isinstance(raw_chat, dict):
        request["chat"] = {
            key: copy.deepcopy(raw_chat[key])
            for key in policy.chat_keys if key in raw_chat
        }
    return request


def _profile_identifier(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
    return str(parsed) if str(parsed) == value.lower() else None


def _profile_text(value: Any, limit: int) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _session_set_surface_whitelist(value: Any, *, policy: SavedSessionPolicy = DEFAULT_POLICY) -> dict[str, Any]:
    """Keep only one work-surface overlay; never accept route secrets or content state."""
    if not isinstance(value, dict):
        return {}
    client = value.get("client")
    surface: dict[str, Any] = {}
    if isinstance(client, str):
        surface["client"] = client
    if isinstance(value.get("project"), str):
        surface["project"] = value["project"]
    if isinstance(value.get("agentHost"), str):
        surface["agentHost"] = value["agentHost"]
    if isinstance(value.get("generation"), dict):
        surface["generation"] = {
            key: copy.deepcopy(value["generation"][key])
            for key in policy.generation_keys if key in value["generation"]
        }
    if client == "chat" and isinstance(value.get("chat"), dict):
        surface["chat"] = {
            key: copy.deepcopy(value["chat"][key])
            for key in policy.chat_keys if key in value["chat"]
        }
    return surface


def _session_set_record_whitelist(value: Any, *, policy: SavedSessionPolicy = DEFAULT_POLICY) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    surfaces = value.get("surfaces")
    return {
        "id": value.get("id"),
        "name": value.get("name"),
        "createdAt": value.get("createdAt"),
        "updatedAt": value.get("updatedAt"),
        "modelName": value.get("modelName"),
        "baseRequest": _profile_request_whitelist(value.get("baseRequest"), policy=policy),
        "_surfaceOverflow": bool(
            isinstance(surfaces, list)
            and len(surfaces) > policy.surface_limit - 1
        ),
        "surfaces": [
            _session_set_surface_whitelist(item, policy=policy)
            for item in surfaces[:policy.surface_limit - 1]
            if isinstance(item, dict)
        ] if isinstance(surfaces, list) else [],
    }


def _session_set_surface_from_request(request: dict[str, Any]) -> dict[str, Any]:
    surface = {
        "client": request["client"],
        "project": request["project"],
        "agentHost": request["agentHost"],
        "generation": copy.deepcopy(request["generation"]),
    }
    if request["client"] == "chat":
        surface["chat"] = copy.deepcopy(request.get("chat") or {
            "systemPrompt": "", "sampling": "model",
        })
    return surface



class SavedSessionStore:
    def __init__(self, *, profile_path: Callable[[], Path], set_path: Callable[[], Path],
                 profile_lock: ContextManager[Any], set_lock: ContextManager[Any],
                 read: Callable[[Path], dict[str, Any]] | None = None,
                 write: Callable[[Path, Any], None] | None = None,
                 validate_request: RequestValidator,
                 validate_binding: Callable[[Any], dict[str, Any] | None],
                 resolve_measured: MeasuredResolver,
                 backend_labels: dict[str, str], client_labels: dict[str, str],
                 now: Callable[[], str], new_id: Callable[[], str],
                 policy: SavedSessionPolicy = DEFAULT_POLICY):
        self.profile_path = profile_path
        self.set_path = set_path
        self.profile_lock = profile_lock
        self.set_lock = set_lock
        self.read = read or self._read_document
        self.write = write or self._write_document
        self.validate_request = validate_request
        self.validate_binding = validate_binding
        self.resolve_measured = resolve_measured
        self.backend_labels = MappingProxyType(dict(backend_labels))
        self.client_labels = MappingProxyType(dict(client_labels))
        self.now = now
        self.new_id = new_id
        self.policy = policy

    def _collection(self, path: Path) -> str:
        return "profiles" if path == self.profile_path() else "sets"

    def _read_document(self, path: Path) -> dict[str, Any]:
        return read_saved_document(path, self._collection(path), self.policy)

    def _write_document(self, path: Path, value: Any) -> None:
        write_saved_document(path, value, self._collection(path), self.policy)

    def _load_launch_profiles_unlocked(self) -> list[dict[str, Any]]:
        data = self.read(self.profile_path())
        if data.get("version") != self.policy.profile_version:
            return []
        raw_profiles = data.get("profiles")
        if not isinstance(raw_profiles, list):
            return []
        profiles: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_profiles:
            if not isinstance(raw, dict):
                continue
            profile_id = _profile_identifier(raw.get("id"))
            name = _profile_text(raw.get("name"), self.policy.profile_name_max).strip()
            policy = str(raw.get("enginePolicy") or "")
            preference = str(raw.get("enginePreference") or "throughput")
            if (
                not profile_id or profile_id in seen or not name
                or policy not in {"fixed", "measured"}
                or preference not in self.policy.preferences
                or not isinstance(raw.get("request"), dict)
            ):
                continue
            binding: dict[str, Any] | None = None
            # Preserve a fail-closed tombstone across unrelated profile writes. A
            # malformed on-disk binding must never be silently laundered into an
            # unbound measured profile on the next load.
            binding_invalid = raw.get("_evidenceBindingInvalid") is True
            if raw.get("evidenceBinding") is not None:
                try:
                    binding = self.validate_binding({
                        "evidenceBinding": raw.get("evidenceBinding"),
                    })
                except ValueError:
                    binding_invalid = True
            seen.add(profile_id)
            profile = {
                "id": profile_id,
                "name": name,
                "createdAt": _profile_text(raw.get("createdAt"), 40),
                "updatedAt": _profile_text(raw.get("updatedAt"), 40),
                "enginePolicy": policy,
                "enginePreference": preference,
                "modelName": _profile_text(raw.get("modelName"), 240),
                "request": _profile_request_whitelist(raw.get("request"), policy=self.policy),
            }
            if binding is not None:
                profile["evidenceBinding"] = binding
            if binding_invalid:
                profile["_evidenceBindingInvalid"] = True
            profiles.append(profile)
            if len(profiles) >= self.policy.profile_limit:
                break
        return profiles

    def load_launch_profiles(self) -> list[dict[str, Any]]:
        with self.profile_lock:
            return self._load_launch_profiles_unlocked()

    def _write_launch_profiles_unlocked(self, profiles: list[dict[str, Any]]) -> None:
        self.write(self.profile_path(), {
            "version": self.policy.profile_version,
            "updatedAt": self.now(),
            "profiles": profiles[:self.policy.profile_limit],
        })

    def launch_profile_inventory(self, models: list[dict[str, Any]]) -> dict[str, Any]:
        profiles: list[dict[str, Any]] = []
        for stored in self.load_launch_profiles():
            item = {
                key: copy.deepcopy(stored[key])
                for key in ("id", "name", "createdAt", "updatedAt", "enginePolicy", "enginePreference", "modelName")
            }
            try:
                if stored.get("_evidenceBindingInvalid") is True:
                    raise ValueError(
                        "This saved measurement reference is invalid. Save the profile again from a completed result."
                    )
                request = self.validate_request(
                    stored["request"], models,
                    preserve_comparison_controls=stored["enginePolicy"] == "measured",
                )
                item["request"] = request
                profile_ready = True
                profile_reason = "Ready to apply."
                if stored["enginePolicy"] == "measured":
                    measured_request = copy.deepcopy(request)
                    measured_request["enginePreference"] = stored["enginePreference"]
                    stored_binding = stored.get("evidenceBinding")
                    if not isinstance(stored_binding, dict):
                        raise ValueError(
                            "Run Calibration once to attach the exact winning engine and settings "
                            "to this measured profile."
                        )
                    measured_request["evidenceBinding"] = copy.deepcopy(stored_binding)
                    result = (
                        self.resolve_measured(measured_request, models, "route")
                        if stored_binding.get("scope") == "route"
                        else self.resolve_measured(measured_request, models, "engine")
                    )
                    resolved_backend = str(result["backend"])
                    tier = str(result.get("engineEvidenceTier") or result.get("evidenceTier") or "")
                    evidence_label = str(result.get("engineEvidenceLabel") or result.get("evidenceLabel") or "Measured engine")
                    rationale = list(result.get("engineRationale") or result.get("rationale") or [])
                    item["resolution"] = {
                        "backend": resolved_backend,
                        "label": self.backend_labels[resolved_backend],
                        "engineChanged": bool(result.get("engineChanged")),
                        "evidenceTier": tier,
                        "evidenceLabel": evidence_label,
                        "trustedWinner": tier == "cross-engine-local-benchmark",
                        "detail": str(rationale[0]) if rationale else evidence_label,
                    }
                    next_action = result.get("engineNextAction")
                    needs_calibration = bool(
                        isinstance(next_action, dict)
                        and (
                            next_action.get("requiresCalibration") is True
                            or next_action.get("id") == "calibrate"
                        )
                    )
                    if needs_calibration:
                        profile_ready = False
                        profile_reason = str(
                            next_action.get("reason")
                            or "Run Calibration before applying this measured profile."
                        )
                    result_binding = (
                        stored_binding
                        if isinstance(stored_binding, dict) else None
                    )
                    validated_binding = (
                        self.validate_binding({
                            "evidenceBinding": result_binding,
                        })
                        if isinstance(result_binding, dict) else None
                    )
                    if validated_binding is None and not needs_calibration:
                        profile_ready = False
                        profile_reason = (
                            "Run Calibration once to attach the exact winning engine and settings "
                            "to this measured profile."
                        )
                    elif validated_binding is not None and not needs_calibration:
                        if validated_binding["preference"] != stored["enginePreference"]:
                            profile_ready = False
                            profile_reason = (
                                "This profile's saved measurement used a different decision goal. "
                                "Run Calibration again."
                            )
                        else:
                            item["evidenceBinding"] = copy.deepcopy(validated_binding)
                else:
                    backend = str(request["backend"])
                    item["resolution"] = {
                        "backend": backend, "label": self.backend_labels[backend],
                        "engineChanged": False, "evidenceTier": "fixed-profile",
                        "evidenceLabel": "Fixed engine", "trustedWinner": False,
                        "detail": "Uses the saved engine and exact visible runtime controls.",
                    }
                item["ready"] = profile_ready
                item["reason"] = profile_reason
            except (ValueError, KeyError, StopIteration) as error:
                item["request"] = _profile_request_whitelist(stored.get("request"), policy=self.policy)
                item["resolution"] = None
                item["ready"] = False
                item["reason"] = str(error) or "This saved route is no longer available."
            profiles.append(item)
        return {
            "profiles": profiles,
            "limit": self.policy.profile_limit,
            "privacy": {
                "settingsOnly": True,
                "storesTranscripts": False,
                "storesCredentials": False,
            },
        }

    def save_launch_profile(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        name_value = payload.get("name")
        if not isinstance(name_value, str):
            raise ValueError("Give this launch profile a name.")
        name = name_value.strip()
        if not name or len(name) > self.policy.profile_name_max or any(ord(character) < 32 for character in name):
            raise ValueError(f"Profile name must be 1 to {self.policy.profile_name_max} visible characters.")
        policy = str(payload.get("enginePolicy") or "fixed")
        if policy not in {"fixed", "measured"}:
            raise ValueError("Choose a fixed engine or an auto measured engine profile.")
        preference = str(payload.get("enginePreference") or "throughput")
        if preference not in self.policy.preferences:
            raise ValueError("Choose a supported measured engine goal.")
        request = self.validate_request(
            payload.get("request"), models, preserve_comparison_controls=policy == "measured",
        )
        model = next(item for item in models if item.get("id") == request["modelId"])
        binding = self.validate_binding(payload)
        if binding is not None and policy != "measured":
            raise ValueError(
                "Only an auto-measured profile can save a completed performance result."
            )
        if policy == "measured":
            if binding is None:
                discovery_request = copy.deepcopy(request)
                discovery_request["enginePreference"] = preference
                discovery = self.resolve_measured(discovery_request, models, "engine")
                next_action = discovery.get("engineNextAction")
                if isinstance(next_action, dict) and (
                    next_action.get("requiresCalibration") is True
                    or next_action.get("id") == "calibrate"
                ):
                    raise ValueError(str(
                        next_action.get("reason")
                        or "Run Calibration before saving an auto-measured profile."
                    ))
                discovered_binding = (
                    discovery.get("engineEvidenceBinding")
                    or discovery.get("evidenceBinding")
                )
                binding = (
                    self.validate_binding({
                        "evidenceBinding": discovered_binding,
                    })
                    if isinstance(discovered_binding, dict) else None
                )
                if binding is None:
                    raise ValueError(
                        "Run Calibration once before saving an auto-measured profile; "
                        "the exact winning engine and settings need a reusable result."
                    )
            if binding.get("preference") != preference:
                raise ValueError(
                    "The completed result used a different goal. Apply it again before saving this profile."
                )
            bound_request = copy.deepcopy(request)
            bound_request.update({
                "enginePreference": preference,
                "evidenceBinding": copy.deepcopy(binding),
            })
            bound_result = (
                self.resolve_measured(bound_request, models, "route")
                if binding["scope"] == "route"
                else self.resolve_measured(bound_request, models, "engine")
            )
            if binding["scope"] == "engine":
                next_action = bound_result.get("engineNextAction")
                if isinstance(next_action, dict) and (
                    next_action.get("requiresCalibration") is True
                    or next_action.get("id") == "calibrate"
                ):
                    raise ValueError(
                        "That measured result no longer matches this profile. "
                        "Run Calibration again before saving it."
                    )
        requested_id = payload.get("id")
        profile_id = _profile_identifier(requested_id) if requested_id not in (None, "") else None
        if requested_id not in (None, "") and not profile_id:
            raise ValueError("The launch profile identifier is invalid.")
        now = self.now()
        with self.profile_lock:
            profiles = self._load_launch_profiles_unlocked()
            index = next((position for position, item in enumerate(profiles) if item["id"] == profile_id), None)
            if profile_id and index is None:
                raise ValueError("That launch profile no longer exists. Refresh the list.")
            duplicate = next(
                (item for item in profiles if item["name"].casefold() == name.casefold() and item["id"] != profile_id),
                None,
            )
            if duplicate:
                raise ValueError("A launch profile already uses that name.")
            if index is None and len(profiles) >= self.policy.profile_limit:
                raise ValueError(f"You can keep at most {self.policy.profile_limit} launch profiles. Delete one before saving another.")
            record = {
                "id": profile_id or str(self.new_id()),
                "name": name,
                "createdAt": profiles[index]["createdAt"] if index is not None else now,
                "updatedAt": now,
                "enginePolicy": policy,
                "enginePreference": preference,
                "modelName": str(model.get("name") or request["modelId"]),
                "request": request,
            }
            if binding is not None:
                record["evidenceBinding"] = copy.deepcopy(binding)
            if index is None:
                profiles.insert(0, record)
            else:
                profiles.pop(index)
                profiles.insert(0, record)
            self._write_launch_profiles_unlocked(profiles)
        return self.launch_profile_inventory(models)

    def delete_launch_profile(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        profile_id = _profile_identifier(payload.get("id"))
        if not profile_id:
            raise ValueError("Choose a valid launch profile to delete.")
        with self.profile_lock:
            profiles = self._load_launch_profiles_unlocked()
            kept = [item for item in profiles if item["id"] != profile_id]
            if len(kept) == len(profiles):
                raise ValueError("That launch profile no longer exists.")
            self._write_launch_profiles_unlocked(kept)
        return self.launch_profile_inventory(models)

    def _load_session_sets_unlocked(self) -> list[dict[str, Any]]:
        data = self.read(self.set_path())
        if data.get("version") != self.policy.set_version:
            return []
        raw_sets = data.get("sets")
        if not isinstance(raw_sets, list):
            return []
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_sets:
            record = _session_set_record_whitelist(raw, policy=self.policy)
            record_id = _profile_identifier(record.get("id"))
            name = _profile_text(record.get("name"), self.policy.set_name_max).strip()
            surfaces = record.get("surfaces")
            if (
                not record_id or record_id in seen or not name
                or not isinstance(record.get("baseRequest"), dict)
                or not isinstance(surfaces, list)
                or record.get("_surfaceOverflow") is True
                or 1 + len(surfaces) > self.policy.surface_limit
            ):
                continue
            seen.add(record_id)
            records.append({
                "id": record_id,
                "name": name,
                "createdAt": _profile_text(record.get("createdAt"), 40),
                "updatedAt": _profile_text(record.get("updatedAt"), 40),
                "modelName": _profile_text(record.get("modelName"), 240),
                "baseRequest": record["baseRequest"],
                "surfaces": surfaces,
            })
            if len(records) >= self.policy.set_limit:
                break
        return records

    def load_session_sets(self) -> list[dict[str, Any]]:
        with self.set_lock:
            return self._load_session_sets_unlocked()

    def _write_session_sets_unlocked(self, records: list[dict[str, Any]]) -> None:
        self.write(self.set_path(), {
            "version": self.policy.set_version,
            "updatedAt": self.now(),
            "sets": records[:self.policy.set_limit],
        })

    def validated_session_set_record(
        self,
        value: Any, models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Revalidate a saved model contract and every surface against current local state."""
        raw = _session_set_record_whitelist(value, policy=self.policy)
        if not isinstance(raw.get("baseRequest"), dict):
            raise ValueError("This Session Set has no primary launch contract.")
        base = self.validate_request(raw["baseRequest"], models)
        raw_surfaces = raw.get("surfaces")
        if (
            raw.get("_surfaceOverflow") is True
            or not isinstance(raw_surfaces, list)
            or 1 + len(raw_surfaces) > self.policy.surface_limit
        ):
            raise ValueError(f"A Session Set can contain at most {self.policy.surface_limit} work surfaces.")
        surfaces: list[dict[str, Any]] = []
        for raw_surface in raw_surfaces:
            surface = _session_set_surface_whitelist(raw_surface, policy=self.policy)
            if not surface.get("client"):
                raise ValueError("A Session Set surface is missing its agent or Chat choice.")
            request = copy.deepcopy(base)
            request.update(surface)
            canonical = self.validate_request(request, models)
            for key in self.policy.shared_engine_keys:
                if canonical.get(key) != base.get(key):
                    raise ValueError("A Session Set surface cannot replace the shared model contract.")
            surfaces.append(_session_set_surface_from_request(canonical))
        return {
            "baseRequest": base,
            "surfaces": surfaces,
        }

    def session_set_requests(
        self,
        value: Any, models: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        validated = self.validated_session_set_record(value, models)
        requests = [copy.deepcopy(validated["baseRequest"])]
        for surface in validated["surfaces"]:
            request = copy.deepcopy(validated["baseRequest"])
            request.update(copy.deepcopy(surface))
            requests.append(self.validate_request(request, models))
        return requests

    def session_set_inventory(self, models: list[dict[str, Any]]) -> dict[str, Any]:
        result: list[dict[str, Any]] = []
        for stored in self.load_session_sets():
            item = {
                key: copy.deepcopy(stored[key])
                for key in ("id", "name", "createdAt", "updatedAt", "modelName")
            }
            try:
                validated = self.validated_session_set_record(stored, models)
                requests = self.session_set_requests(validated, models)
                clients = [str(request["client"]) for request in requests]
                terminal_count = sum(
                    1 for request in requests
                    if request["client"] != "chat" and request["agentHost"] == "terminal"
                )
                item.update({
                    "baseRequest": validated["baseRequest"],
                    "surfaces": validated["surfaces"],
                    "surfaceCount": len(requests),
                    "surfaceLabels": [self.client_labels.get(client, client) for client in clients],
                    "terminalCount": terminal_count,
                    "ready": True,
                    "reason": "Ready to plan.",
                })
            except (KeyError, StopIteration, ValueError) as error:
                item.update({
                    "baseRequest": _profile_request_whitelist(stored.get("baseRequest"), policy=self.policy),
                    "surfaces": [
                        _session_set_surface_whitelist(surface, policy=self.policy)
                        for surface in stored.get("surfaces", [])
                    ],
                    "surfaceCount": 1 + len(stored.get("surfaces", [])),
                    "surfaceLabels": [],
                    "terminalCount": 0,
                    "ready": False,
                    "reason": str(error) or "This Session Set is no longer available.",
                })
            result.append(item)
        return {
            "version": self.policy.set_version,
            "sets": result,
            "limit": self.policy.set_limit,
            "surfaceLimit": self.policy.surface_limit,
            "privacy": {
                "settingsOnly": True,
                "storesTranscripts": False,
                "storesConsoleOutput": False,
                "storesCredentials": False,
                "storesPorts": False,
            },
        }

    def save_active_session_set(
        self,
        payload: dict[str, Any], models: list[dict[str, Any]], capture_active_requests: Callable[[], tuple[dict[str, Any], list[dict[str, Any]]]],
    ) -> dict[str, Any]:
        name_value = payload.get("name")
        if not isinstance(name_value, str):
            raise ValueError("Give this Session Set a name.")
        name = name_value.strip()
        if not name or len(name) > self.policy.set_name_max or any(ord(character) < 32 for character in name):
            raise ValueError(f"Session Set name must be 1 to {self.policy.set_name_max} visible characters.")
        requested_id = payload.get("id")
        record_id = _profile_identifier(requested_id) if requested_id not in (None, "") else None
        if requested_id not in (None, "") and not record_id:
            raise ValueError("The Session Set identifier is invalid.")
        base_payload, attached_payloads = capture_active_requests()
        base = self.validate_request(base_payload, models)
        surfaces: list[dict[str, Any]] = []
        for attached_payload in attached_payloads:
            canonical = self.validate_request(attached_payload, models)
            for key in self.policy.shared_engine_keys:
                if canonical.get(key) != base.get(key):
                    raise ValueError("An active surface no longer matches the shared model contract.")
            surfaces.append(_session_set_surface_from_request(canonical))
        if 1 + len(surfaces) > self.policy.surface_limit:
            raise ValueError(f"A Session Set can contain at most {self.policy.surface_limit} work surfaces.")
        model = next(item for item in models if item.get("id") == base["modelId"])
        now = self.now()
        with self.set_lock:
            records = self._load_session_sets_unlocked()
            index = next((position for position, item in enumerate(records) if item["id"] == record_id), None)
            if record_id and index is None:
                raise ValueError("That Session Set no longer exists. Refresh the list.")
            duplicate = next(
                (item for item in records if item["name"].casefold() == name.casefold() and item["id"] != record_id),
                None,
            )
            if duplicate:
                raise ValueError("A Session Set already uses that name.")
            if index is None and len(records) >= self.policy.set_limit:
                raise ValueError(f"You can keep at most {self.policy.set_limit} Session Sets. Delete one first.")
            record = {
                "id": record_id or str(self.new_id()),
                "name": name,
                "createdAt": records[index]["createdAt"] if index is not None else now,
                "updatedAt": now,
                "modelName": str(model.get("name") or base["modelId"]),
                "baseRequest": base,
                "surfaces": surfaces,
            }
            if index is not None:
                records.pop(index)
            records.insert(0, record)
            self._write_session_sets_unlocked(records)
        return self.session_set_inventory(models)

    def delete_session_set(self, payload: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
        record_id = _profile_identifier(payload.get("id"))
        if not record_id:
            raise ValueError("Choose a valid Session Set to delete.")
        with self.set_lock:
            records = self._load_session_sets_unlocked()
            kept = [item for item in records if item["id"] != record_id]
            if len(kept) == len(records):
                raise ValueError("That Session Set no longer exists.")
            self._write_session_sets_unlocked(kept)
        return self.session_set_inventory(models)
