"""Canonical, fail-closed sampling contracts for launcher-owned requests.

This module is intentionally dependency-free and has no launcher imports so the
same file can live beside the HTTP runtime proxies.  A serialized contract is a
small JSON object that explicitly proves the launcher owns sampling for a route::

    {
      "schemaVersion": 1,
      "controlled": true,
      "mode": "model",
      "values": {"temperature": 0.7, "top_p": 0.9}
    }

Request rewriting removes every launcher-supported sampling field supplied by a
client and then writes the contract values.  Callers must state which fields the
exact upstream route can represent; a contract using any other field is rejected
instead of being silently weakened.  A pinned route may explicitly declare that
it implements model defaults internally, but that exception never applies to a
custom contract.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


SAMPLING_CONTRACT_SCHEMA_VERSION = 1

# Ordering here is part of the canonical in-memory representation.  JSON output
# is additionally key-sorted, so fingerprints do not depend on input ordering.
SUPPORTED_SAMPLING_FIELDS = (
    "temperature",
    "top_p",
    "top_k",
    "presence_penalty",
    "frequency_penalty",
    "repetition_penalty",
    "seed",
)

# These are sampling/decoding controls used by common OpenAI-compatible, llama.cpp,
# and Transformers servers but not owned by this contract version. Preserving one
# would let the client alter a calibrated request, so rewrite helpers reject it
# explicitly. Families whose members vary by runtime are covered by the prefixes
# below as well as this stable set of known spellings.
NON_CONTRACT_SAMPLING_FIELDS = frozenset({
    "bad_words_ids",
    "begin_suppress_tokens",
    "best_of",
    "diversity_penalty",
    "do_sample",
    "early_stopping",
    "encoder_no_repeat_ngram_size",
    "epsilon_cutoff",
    "eta_cutoff",
    "exponential_decay_length_penalty",
    "generation_config",
    "generation_kwargs",
    "generation_parameters",
    "generation_params",
    "ignore_eos",
    "length_penalty",
    "logit_bias",
    "logit_processor",
    "logits_processor",
    "logits_processors",
    "min_keep",
    "min_p",
    "mirostat",
    "mirostat_eta",
    "mirostat_tau",
    "no_repeat_ngram_size",
    "num_beam_groups",
    "num_beams",
    "penalize_nl",
    "renormalize_logits",
    "repeat_last_n",
    "repeat_penalty",
    "remove_invalid_values",
    "repetition_context_size",
    "sampler",
    "sampler_order",
    "samplers",
    "sampling_parameters",
    "sampling_params",
    "sampling_settings",
    "sequence_bias",
    "suppress_tokens",
    "tail_free_sampling_z",
    "tfs_z",
    "token_bias",
    "top_a",
    "typ_p",
    "typical_p",
    "use_beam_search",
    "xtc_probability",
    "xtc_threshold",
})

_NON_CONTRACT_SAMPLING_PREFIXES = (
    "beam_",
    "dry_",
    "dynatemp_",
    "logits_",
    "mirostat_",
    "repeat_",
    "repetition_",
    "sampler_",
    "sampling_",
    "typical_",
    "xtc_",
)

_CAMEL_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

_FLOAT_BOUNDS = {
    "temperature": (0.0, 2.0),
    "top_p": (0.0, 1.0),
    "presence_penalty": (-2.0, 2.0),
    "frequency_penalty": (-2.0, 2.0),
    "repetition_penalty": (0.0, 10.0),
}
_INTEGER_BOUNDS = {
    "top_k": (0, 1_000_000),
    "seed": (0, 4_294_967_295),
}
_DOCUMENT_KEYS = frozenset({"schemaVersion", "controlled", "mode", "values"})


class SamplingContractError(ValueError):
    """Base class for invalid or unenforceable sampling contracts."""


class SamplingValidationError(SamplingContractError):
    """A contract or sampling value is malformed."""


class SamplingRepresentabilityError(SamplingContractError):
    """The selected upstream protocol cannot express the exact contract."""

    def __init__(self, protocol: str, fields: Iterable[str]) -> None:
        self.protocol = protocol
        self.fields = tuple(sorted({str(field) for field in fields}))
        joined = ", ".join(self.fields)
        super().__init__(
            f"{protocol} cannot represent the sampling contract fields: {joined}."
        )


class SamplingRequestError(SamplingContractError):
    """A live request contains sampling controls outside this contract."""

    def __init__(self, protocol: str, fields: Iterable[str]) -> None:
        self.protocol = protocol
        self.fields = tuple(sorted({str(field) for field in fields}))
        joined = ", ".join(self.fields)
        super().__init__(
            f"{protocol} request contains uncontrolled sampling fields: {joined}."
        )


@dataclass(frozen=True)
class SamplingContract:
    """Immutable canonical contract.

    Construct contracts with :func:`build_sampling_contract` or
    :func:`load_sampling_contract`.  Values are stored as an ordered tuple so a
    caller cannot mutate a verified contract after its fingerprint is computed.
    """

    mode: str
    _items: tuple[tuple[str, int | float], ...]

    def __post_init__(self) -> None:
        if self.mode not in {"model", "custom"}:
            raise SamplingValidationError(
                "Sampling mode must be either 'model' or 'custom'."
            )
        canonical = canonicalize_sampling(dict(self._items))
        expected = tuple(
            (field, canonical[field])
            for field in SUPPORTED_SAMPLING_FIELDS
            if field in canonical
        )
        if self._items != expected:
            raise SamplingValidationError("Sampling contract values are not canonical.")
        if self.mode == "custom" and not self._items:
            raise SamplingValidationError(
                "Custom sampling must set at least one supported field."
            )

    @property
    def values(self) -> dict[str, int | float]:
        """Return a fresh JSON-compatible copy of the canonical values."""
        return dict(self._items)

    def as_dict(self) -> dict[str, Any]:
        """Return the strict document stored in proxy configuration/evidence."""
        return {
            "schemaVersion": SAMPLING_CONTRACT_SCHEMA_VERSION,
            "controlled": True,
            "mode": self.mode,
            "values": self.values,
        }


def _field_list(values: Iterable[Any]) -> str:
    return ", ".join(sorted(repr(value) for value in values))


def _normalized_request_field(value: Any) -> str:
    """Normalize spelling only for detecting sampler aliases.

    Wire field names remain case-sensitive and are never rewritten through
    this helper.  Treating ``topP`` or ``logitBias`` as unknown pass-through
    metadata would let a permissive runtime interpret a client-controlled
    sampler beside the launcher's canonical snake-case contract.
    """
    raw = str(value)
    return _CAMEL_CASE_BOUNDARY.sub("_", raw).replace("-", "_").casefold()


def _canonical_float(field: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SamplingValidationError(f"{field} must be a JSON number.")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise SamplingValidationError(f"{field} must be finite.")
    low, high = _FLOAT_BOUNDS[field]
    if not low <= parsed <= high:
        raise SamplingValidationError(
            f"{field} must be between {low:g} and {high:g}."
        )
    # Collapse negative zero so semantically identical inputs serialize equally.
    return 0.0 if parsed == 0.0 else parsed


def _canonical_integer(field: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SamplingValidationError(f"{field} must be a JSON integer.")
    if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
        raise SamplingValidationError(f"{field} must be a JSON integer.")
    parsed = int(value)
    low, high = _INTEGER_BOUNDS[field]
    if not low <= parsed <= high:
        raise SamplingValidationError(
            f"{field} must be between {low:,} and {high:,}."
        )
    return parsed


def canonicalize_sampling(values: Mapping[str, Any] | None) -> dict[str, int | float]:
    """Validate and canonicalize all sampling fields supported by version 1.

    ``None`` values mean "not set" and are omitted.  Unknown fields, booleans,
    numeric strings, non-finite values, and out-of-range values are rejected.
    """
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise SamplingValidationError("Sampling values must be a JSON object.")
    unknown = set(values) - set(SUPPORTED_SAMPLING_FIELDS)
    if unknown:
        raise SamplingValidationError(
            f"Unsupported sampling fields: {_field_list(unknown)}."
        )
    result: dict[str, int | float] = {}
    for field in SUPPORTED_SAMPLING_FIELDS:
        value = values.get(field)
        if value is None:
            continue
        if field in _FLOAT_BOUNDS:
            result[field] = _canonical_float(field, value)
        else:
            result[field] = _canonical_integer(field, value)
    return result


def _contract_from_values(mode: str, values: Mapping[str, Any] | None) -> SamplingContract:
    canonical = canonicalize_sampling(values)
    items = tuple(
        (field, canonical[field])
        for field in SUPPORTED_SAMPLING_FIELDS
        if field in canonical
    )
    return SamplingContract(mode=mode, _items=items)


def build_sampling_contract(
    mode: str,
    *,
    model_defaults: Mapping[str, Any] | None = None,
    custom: Mapping[str, Any] | None = None,
) -> SamplingContract:
    """Resolve a model-default or custom selection into one exact contract.

    Model mode snapshots the model defaults.  Custom mode uses exactly the
    caller-supplied fields and deliberately does not invent or merge defaults.
    This keeps every effective value visible to the launcher.
    """
    if mode == "model":
        if custom is not None and canonicalize_sampling(custom):
            raise SamplingValidationError(
                "Model-default sampling cannot also contain custom values."
            )
        return _contract_from_values(mode, model_defaults)
    if mode == "custom":
        if custom is None:
            raise SamplingValidationError("Custom sampling values are required.")
        return _contract_from_values(mode, custom)
    raise SamplingValidationError("Sampling mode must be either 'model' or 'custom'.")


def load_sampling_contract(document: Mapping[str, Any]) -> SamplingContract:
    """Load a strict serialized contract and reject legacy/uncontrolled forms."""
    if not isinstance(document, Mapping):
        raise SamplingValidationError("Sampling contract must be a JSON object.")
    unknown = set(document) - _DOCUMENT_KEYS
    missing = _DOCUMENT_KEYS - set(document)
    if unknown:
        raise SamplingValidationError(
            f"Unsupported sampling contract keys: {_field_list(unknown)}."
        )
    if missing:
        raise SamplingValidationError(
            f"Sampling contract is missing keys: {_field_list(missing)}."
        )
    schema_version = document.get("schemaVersion")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != SAMPLING_CONTRACT_SCHEMA_VERSION
    ):
        raise SamplingValidationError("Unsupported sampling contract schema version.")
    if document.get("controlled") is not True:
        raise SamplingValidationError("Sampling contract is not launcher-controlled.")
    mode = document.get("mode")
    if not isinstance(mode, str):
        raise SamplingValidationError("Sampling contract mode must be text.")
    values = document.get("values")
    if not isinstance(values, Mapping):
        raise SamplingValidationError("Sampling contract values must be a JSON object.")
    return _contract_from_values(mode, values)


def _validated_contract(value: SamplingContract | Mapping[str, Any]) -> SamplingContract:
    if isinstance(value, SamplingContract):
        # Rebuild so even a manually-constructed object follows all invariants.
        return _contract_from_values(value.mode, value.values)
    return load_sampling_contract(value)


def serialize_sampling_contract(
    contract: SamplingContract | Mapping[str, Any],
) -> str:
    """Return the deterministic JSON representation used for hashing/storage."""
    value = _validated_contract(contract)
    return json.dumps(
        value.as_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sampling_fingerprint(contract: SamplingContract | Mapping[str, Any]) -> str:
    """Return SHA-256 of the exact canonical serialized contract."""
    serialized = serialize_sampling_contract(contract).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _representable_field_set(
    fields: Iterable[str], *, protocol: str,
) -> frozenset[str]:
    if isinstance(fields, (str, bytes)):
        raise SamplingRepresentabilityError(protocol, (str(fields),))
    try:
        values = frozenset(fields)
    except TypeError as error:
        raise SamplingRepresentabilityError(protocol, ("<invalid field set>",)) from error
    invalid = {field for field in values if field not in SUPPORTED_SAMPLING_FIELDS}
    if invalid:
        raise SamplingRepresentabilityError(protocol, invalid)
    return values


def _rewrite_sampling_request(
    request: Mapping[str, Any],
    contract: SamplingContract | Mapping[str, Any],
    *,
    representable_fields: Iterable[str],
    implicit_model_defaults: bool,
    protocol: str,
) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise SamplingRequestError(protocol, ("<non-object request>",))
    value = _validated_contract(contract)
    representable = _representable_field_set(
        representable_fields, protocol=protocol,
    )
    contract_values = value.values
    contract_fields = set(contract_values)
    unrepresentable = contract_fields - representable
    if value.mode == "model" and implicit_model_defaults:
        # A pinned runtime may own some or all packaged defaults without
        # accepting them as request fields.  This exception is explicit at the
        # route boundary; custom contracts never receive it.
        unrepresentable = set()
    if unrepresentable:
        raise SamplingRepresentabilityError(protocol, unrepresentable)
    uncontrolled = set()
    for field in request:
        field_name = str(field)
        normalized = _normalized_request_field(field_name)
        supported_alias = (
            normalized in SUPPORTED_SAMPLING_FIELDS
            and field_name not in SUPPORTED_SAMPLING_FIELDS
        )
        non_contract = (
            normalized in NON_CONTRACT_SAMPLING_FIELDS
            or any(
                normalized.startswith(prefix)
                for prefix in _NON_CONTRACT_SAMPLING_PREFIXES
            )
        )
        if supported_alias or (
            non_contract and normalized not in SUPPORTED_SAMPLING_FIELDS
        ):
            uncontrolled.add(field_name)
    if uncontrolled:
        raise SamplingRequestError(protocol, uncontrolled)

    rewritten = dict(request)
    for field in SUPPORTED_SAMPLING_FIELDS:
        rewritten.pop(field, None)
    rewritten.update({
        field: setting
        for field, setting in contract_values.items()
        if field in representable
    })
    return rewritten


def rewrite_chat_completions_request(
    request: Mapping[str, Any],
    contract: SamplingContract | Mapping[str, Any],
    *,
    representable_fields: Iterable[str],
    implicit_model_defaults: bool = False,
) -> dict[str, Any]:
    """Enforce a contract on a Chat Completions JSON object.

    ``representable_fields`` is mandatory and must describe the exact selected
    runtime/version, not Chat Completions in the abstract.  Set
    ``implicit_model_defaults`` only for a pinned runtime whose packaged sampler
    has been independently verified against the selected model artifact.
    """
    return _rewrite_sampling_request(
        request,
        contract,
        representable_fields=representable_fields,
        implicit_model_defaults=implicit_model_defaults,
        protocol="Chat Completions",
    )


def rewrite_responses_request(
    request: Mapping[str, Any],
    contract: SamplingContract | Mapping[str, Any],
    *,
    representable_fields: Iterable[str],
    implicit_model_defaults: bool = False,
) -> dict[str, Any]:
    """Enforce a contract on a Responses JSON object, failing on field loss."""
    return _rewrite_sampling_request(
        request,
        contract,
        representable_fields=representable_fields,
        implicit_model_defaults=implicit_model_defaults,
        protocol="Responses",
    )


__all__ = [
    "NON_CONTRACT_SAMPLING_FIELDS",
    "SAMPLING_CONTRACT_SCHEMA_VERSION",
    "SUPPORTED_SAMPLING_FIELDS",
    "SamplingContract",
    "SamplingContractError",
    "SamplingRepresentabilityError",
    "SamplingRequestError",
    "SamplingValidationError",
    "build_sampling_contract",
    "canonicalize_sampling",
    "load_sampling_contract",
    "rewrite_chat_completions_request",
    "rewrite_responses_request",
    "sampling_fingerprint",
    "serialize_sampling_contract",
]
