from __future__ import annotations

import hashlib
import json
import math
import unittest

import codex_proxy
import sampling_contract as sampling
import session_proxy


ALL_FIELDS = frozenset(sampling.SUPPORTED_SAMPLING_FIELDS)


class SamplingCanonicalizationTests(unittest.TestCase):
    def test_canonicalizes_every_supported_field_in_one_stable_order(self) -> None:
        canonical = sampling.canonicalize_sampling({
            "seed": 17.0,
            "repetition_penalty": 1,
            "frequency_penalty": -0.0,
            "presence_penalty": -0.25,
            "top_k": 40.0,
            "top_p": 1,
            "temperature": 0,
        })
        self.assertEqual(list(canonical), list(sampling.SUPPORTED_SAMPLING_FIELDS))
        self.assertEqual(canonical, {
            "temperature": 0.0,
            "top_p": 1.0,
            "top_k": 40,
            "presence_penalty": -0.25,
            "frequency_penalty": 0.0,
            "repetition_penalty": 1.0,
            "seed": 17,
        })
        self.assertIsInstance(canonical["temperature"], float)
        self.assertIsInstance(canonical["top_k"], int)

    def test_none_means_omitted_and_model_defaults_may_be_empty(self) -> None:
        self.assertEqual(
            sampling.canonicalize_sampling({"temperature": None, "seed": None}),
            {},
        )
        contract = sampling.build_sampling_contract("model", model_defaults=None)
        self.assertEqual(contract.values, {})

    def test_rejects_unknown_non_numeric_non_finite_and_out_of_range_values(self) -> None:
        invalid_values = (
            {"min_p": 0.1},
            {"temperature": True},
            {"temperature": "0.7"},
            {"temperature": math.nan},
            {"top_p": math.inf},
            {"temperature": 2.01},
            {"top_p": -0.01},
            {"repetition_penalty": 10.01},
            {"presence_penalty": -2.01},
            {"frequency_penalty": 2.01},
            {"top_k": 1.5},
            {"top_k": 1_000_001},
            {"seed": -1},
            {"seed": 4_294_967_296},
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(sampling.SamplingValidationError):
                    sampling.canonicalize_sampling(value)

    def test_model_and_custom_modes_cannot_be_ambiguous(self) -> None:
        model = sampling.build_sampling_contract(
            "model", model_defaults={"temperature": 0.6},
        )
        custom = sampling.build_sampling_contract(
            "custom", custom={"temperature": 0.6},
        )
        self.assertEqual(model.values, custom.values)
        self.assertEqual(model.mode, "model")
        self.assertEqual(custom.mode, "custom")
        with self.assertRaises(sampling.SamplingValidationError):
            sampling.build_sampling_contract(
                "model",
                model_defaults={"temperature": 0.6},
                custom={"top_p": 0.9},
            )
        for custom_values in (None, {}):
            with self.subTest(custom=custom_values):
                with self.assertRaises(sampling.SamplingValidationError):
                    sampling.build_sampling_contract("custom", custom=custom_values)


class SamplingSerializationTests(unittest.TestCase):
    def test_serialization_and_fingerprint_are_deterministic(self) -> None:
        first = sampling.build_sampling_contract("model", model_defaults={
            "repetition_penalty": 1,
            "temperature": 1,
            "top_k": 20.0,
        })
        second = sampling.build_sampling_contract("model", model_defaults={
            "top_k": 20,
            "temperature": 1.0,
            "repetition_penalty": 1.0,
        })
        expected = (
            '{"controlled":true,"mode":"model","schemaVersion":1,'
            '"values":{"repetition_penalty":1.0,"temperature":1.0,"top_k":20}}'
        )
        self.assertEqual(sampling.serialize_sampling_contract(first), expected)
        self.assertEqual(sampling.serialize_sampling_contract(second), expected)
        self.assertEqual(
            sampling.sampling_fingerprint(first),
            hashlib.sha256(expected.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            sampling.sampling_fingerprint(first),
            sampling.sampling_fingerprint(second),
        )

    def test_mode_and_repetition_penalty_are_bound_into_fingerprint(self) -> None:
        model = sampling.build_sampling_contract(
            "model", model_defaults={"repetition_penalty": 1.0},
        )
        custom = sampling.build_sampling_contract(
            "custom", custom={"repetition_penalty": 1.0},
        )
        changed = sampling.build_sampling_contract(
            "model", model_defaults={"repetition_penalty": 1.1},
        )
        self.assertNotEqual(
            sampling.sampling_fingerprint(model),
            sampling.sampling_fingerprint(custom),
        )
        self.assertNotEqual(
            sampling.sampling_fingerprint(model),
            sampling.sampling_fingerprint(changed),
        )

    def test_strict_load_round_trip_rejects_legacy_or_uncontrolled_evidence(self) -> None:
        source = sampling.build_sampling_contract(
            "custom", custom={"temperature": 0.2, "seed": 42},
        )
        document = json.loads(sampling.serialize_sampling_contract(source))
        loaded = sampling.load_sampling_contract(document)
        self.assertEqual(loaded, source)

        invalid_documents = (
            {"mode": "custom", "values": {"temperature": 0.2}},
            {**document, "schemaVersion": 0},
            {**document, "schemaVersion": True},
            {**document, "controlled": False},
            {**document, "extra": "silently ignored"},
        )
        for invalid in invalid_documents:
            with self.subTest(document=invalid):
                with self.assertRaises(sampling.SamplingValidationError):
                    sampling.load_sampling_contract(invalid)

    def test_returned_values_cannot_mutate_the_contract(self) -> None:
        contract = sampling.build_sampling_contract(
            "model", model_defaults={"temperature": 0.7},
        )
        exposed = contract.values
        exposed["temperature"] = 1.9
        self.assertEqual(contract.values, {"temperature": 0.7})


class SamplingRequestRewriteTests(unittest.TestCase):
    def test_chat_rewrite_replaces_client_sampling_and_preserves_other_fields(self) -> None:
        contract = sampling.build_sampling_contract("custom", custom={
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 12,
            "presence_penalty": 0.1,
            "frequency_penalty": -0.1,
            "repetition_penalty": 1.05,
            "seed": 99,
        })
        request = {
            "model": "served-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
            "temperature": 1.8,
            "top_p": 0.1,
            "top_k": 999,
            "presence_penalty": 2,
            "frequency_penalty": 2,
            "repetition_penalty": 2,
            "seed": 1,
        }
        original = dict(request)
        rewritten = sampling.rewrite_chat_completions_request(
            request, contract, representable_fields=ALL_FIELDS,
        )
        self.assertEqual(request, original)
        self.assertEqual(rewritten["model"], "served-model")
        self.assertIs(rewritten["messages"], request["messages"])
        self.assertTrue(rewritten["stream"])
        self.assertEqual(
            {field: rewritten[field] for field in sampling.SUPPORTED_SAMPLING_FIELDS},
            contract.values,
        )

    def test_model_contract_strips_client_fields_omitted_by_model_defaults(self) -> None:
        contract = sampling.build_sampling_contract(
            "model", model_defaults={"temperature": 0.7},
        )
        rewritten = sampling.rewrite_chat_completions_request(
            {"model": "served", "temperature": 1.5, "top_p": 0.2, "seed": 8},
            contract,
            representable_fields={"temperature"},
        )
        self.assertEqual(rewritten, {"model": "served", "temperature": 0.7})

    def test_pinned_route_may_explicitly_use_implicit_model_defaults_only(self) -> None:
        model_contract = sampling.build_sampling_contract("model", model_defaults={
            "temperature": 0.7, "top_k": 40,
        })
        rewritten = sampling.rewrite_chat_completions_request(
            {"model": "served", "temperature": 1.5, "top_k": 2},
            model_contract,
            representable_fields=set(),
            implicit_model_defaults=True,
        )
        self.assertEqual(rewritten, {"model": "served"})

        custom_contract = sampling.build_sampling_contract(
            "custom", custom={"temperature": 0.7},
        )
        with self.assertRaises(sampling.SamplingRepresentabilityError):
            sampling.rewrite_chat_completions_request(
                {"model": "served"},
                custom_contract,
                representable_fields=set(),
                implicit_model_defaults=True,
            )

    def test_unrepresentable_contract_fails_closed_for_responses(self) -> None:
        contract = sampling.build_sampling_contract("custom", custom={
            "temperature": 0.3,
            "top_k": 40,
            "repetition_penalty": 1.1,
        })
        request = {"model": "served", "input": "Hello", "temperature": 1.0}
        with self.assertRaises(sampling.SamplingRepresentabilityError) as raised:
            sampling.rewrite_responses_request(
                request,
                contract,
                representable_fields={"temperature", "top_p", "seed"},
            )
        self.assertEqual(
            raised.exception.fields,
            ("repetition_penalty", "top_k"),
        )
        self.assertEqual(request["temperature"], 1.0)

    def test_responses_rewrite_works_when_exact_contract_is_representable(self) -> None:
        contract = sampling.build_sampling_contract("custom", custom={
            "temperature": 0.3, "top_p": 0.9, "seed": 7,
        })
        rewritten = sampling.rewrite_responses_request(
            {
                "model": "served", "input": "Hello",
                "temperature": 2.0, "top_p": 0.1, "seed": 99,
                "top_k": 50, "presence_penalty": 1.0,
            },
            contract,
            representable_fields={"temperature", "top_p", "seed"},
        )
        self.assertEqual(rewritten, {
            "model": "served", "input": "Hello",
            "temperature": 0.3, "top_p": 0.9, "seed": 7,
        })

    def test_known_non_contract_sampling_extensions_are_rejected(self) -> None:
        contract = sampling.build_sampling_contract(
            "model", model_defaults={"temperature": 0.7},
        )
        for helper in (
            sampling.rewrite_chat_completions_request,
            sampling.rewrite_responses_request,
        ):
            with self.subTest(helper=helper.__name__):
                with self.assertRaises(sampling.SamplingRequestError) as raised:
                    helper(
                        {"model": "served", "min_p": 0.05, "typical_p": 0.9},
                        contract,
                        representable_fields={"temperature"},
                    )
                self.assertEqual(raised.exception.fields, ("min_p", "typical_p"))

    def test_runtime_sampler_families_are_rejected_without_blocking_other_fields(self) -> None:
        contract = sampling.build_sampling_contract(
            "model", model_defaults={"temperature": 0.7},
        )
        uncontrolled = {
            "logit_bias": {"42": 10},
            "logitBias": {"43": -5},
            "dynatemp_range": 0.5,
            "dynatempRange": 0.25,
            "dynatemp_future_mode": "adaptive",
            "dry_multiplier": 0.8,
            "dry_future_window": 2_048,
            "repetition_context_size": 256,
            "repetitionContextSize": 128,
            "samplers": ["top_k", "temperature"],
            "sampler_priority": "custom",
            "sampling_params": {"temperature": 1.9},
            "generation_config": {"do_sample": True},
            "repeat_penalty": 1.2,
            "xtc_probability": 0.1,
            "topP": 0.2,
            "Temperature": 1.9,
        }
        for helper in (
            sampling.rewrite_chat_completions_request,
            sampling.rewrite_responses_request,
        ):
            with self.subTest(helper=helper.__name__):
                with self.assertRaises(sampling.SamplingRequestError) as raised:
                    helper(
                        {
                            "model": "served",
                            "metadata": {"trace": "preserve-me"},
                            **uncontrolled,
                        },
                        contract,
                        representable_fields={"temperature"},
                    )
                self.assertEqual(
                    raised.exception.fields,
                    tuple(sorted(uncontrolled)),
                )

        preserved = sampling.rewrite_chat_completions_request(
            {
                "model": "served",
                "messages": [{"role": "user", "content": "Hello"}],
                "tools": [{"type": "function", "function": {"name": "lookup"}}],
                "tool_choice": "auto",
                "response_format": {"type": "json_object"},
                "stop": ["END"],
                "cache_prompt": True,
                "metadata": {"trace": "preserve-me"},
            },
            contract,
            representable_fields={"temperature"},
        )
        self.assertEqual(preserved["temperature"], 0.7)
        for field in (
            "messages", "tools", "tool_choice", "response_format", "stop",
            "cache_prompt", "metadata",
        ):
            self.assertIn(field, preserved)

    def test_live_chat_and_responses_transforms_reject_uncontrolled_samplers(self) -> None:
        contract = sampling.build_sampling_contract(
            "model", model_defaults={"temperature": 0.7},
        ).as_dict()
        chat_policy = {
            "samplingContract": contract,
            "samplingEnforcement": {
                "protocol": "chat-completions",
                "representableFields": ["temperature"],
                "implicitModelDefaults": False,
            },
        }
        response_policy = {
            "samplingContract": contract,
            "samplingEnforcement": {
                "protocol": "responses",
                "representableFields": ["temperature"],
                "implicitModelDefaults": False,
            },
        }
        chat_config = {
            "servedModel": "served", "outputLimit": 256,
            "backend": "lmstudio", "reasoning": "auto",
        }
        response_config = {
            "servedModel": "served", "outputLimit": 256,
            "backend": "lmstudio", "reasoning": "auto",
            **response_policy,
        }

        with self.assertRaisesRegex(ValueError, "uncontrolled sampling fields"):
            session_proxy.transform_chat_request(
                json.dumps({
                    "model": "served", "messages": [],
                    "logit_bias": {"42": 10}, "dry_multiplier": 0.8,
                }).encode("utf-8"),
                chat_config,
                chat_policy,
            )
        with self.assertRaisesRegex(ValueError, "uncontrolled sampling fields"):
            codex_proxy.transform_response_request(
                json.dumps({
                    "model": "served", "input": "Hello",
                    "samplers": ["top_k"], "dynatemp_range": 0.5,
                }).encode("utf-8"),
                response_config,
            )

    def test_representability_declaration_is_mandatory_and_strict(self) -> None:
        contract = sampling.build_sampling_contract(
            "model", model_defaults={"temperature": 0.7},
        )
        with self.assertRaises(TypeError):
            sampling.rewrite_chat_completions_request(  # type: ignore[call-arg]
                {"model": "served"}, contract,
            )
        with self.assertRaises(sampling.SamplingRepresentabilityError):
            sampling.rewrite_chat_completions_request(
                {"model": "served"},
                contract,
                representable_fields={"temperature", "min_p"},
            )
        with self.assertRaises(sampling.SamplingRepresentabilityError):
            sampling.rewrite_chat_completions_request(
                {"model": "served"},
                contract,
                representable_fields={"temperature", 7},  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
