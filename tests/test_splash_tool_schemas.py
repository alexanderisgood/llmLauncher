"""Tool-schema compatibility for the Splash route.

Splash compiles each tool's parameters into an llguidance grammar and refuses
a fixed set of keywords at the schema root. Pi's ``browser_check`` declares
cross-field requirements with a top-level ``anyOf``, so the relay forwards the
base object schema; the tool itself still validates every argument.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import session_proxy  # noqa: E402
import splash_runtime  # noqa: E402

ACTIONS = ["open", "inspect", "resize", "screenshot", "click", "fill", "press", "evaluate", "close"]
REQUIRED_FIELDS = {
    "open": ["url"], "inspect": [], "resize": ["width", "height"], "screenshot": [],
    "click": ["selector"], "fill": ["selector", "text"], "press": ["key"],
    "evaluate": ["script"], "close": [], "sequence": ["steps"],
}


def action_alternatives(names: list[str]) -> list[dict]:
    return [
        {"properties": {"action": {"const": name}}, "required": REQUIRED_FIELDS[name]}
        for name in names
    ]


def browser_check_schema() -> dict:
    """The shape ``pi-browser.js`` registers today."""
    properties = {
        "action": {"type": "string", "enum": ACTIONS + ["sequence"]},
        "url": {"type": "string", "minLength": 1},
        "selector": {"type": "string", "minLength": 1},
        "text": {"type": "string"},
        "key": {"type": "string", "minLength": 1},
        "width": {"type": "integer", "minimum": 320, "maximum": 2560},
        "height": {"type": "integer", "minimum": 240, "maximum": 1600},
        "script": {"type": "string", "minLength": 1, "maxLength": 12000},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "anyOf": action_alternatives(ACTIONS + ["sequence"]),
        "required": ["action"],
        "properties": {
            **properties,
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action"],
                    "properties": properties,
                    "anyOf": action_alternatives(ACTIONS),
                },
            },
        },
    }


ENGINE_PYTHON = pathlib.Path("/opt/homebrew/opt/splash/libexec/python/bin/python3")
ENGINE_SERVER = pathlib.Path("/opt/homebrew/opt/splash/libexec/server")


def compile_with_engine(schema: dict) -> subprocess.CompletedProcess:
    """Run the installed engine's own tool-schema compiler on ``schema``."""
    script = (
        "import importlib.util, json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "spec = importlib.util.spec_from_file_location('splash_tool_schema', sys.argv[2])\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['splash_tool_schema'] = module\n"
        "spec.loader.exec_module(module)\n"
        "grammar = module._tool_arguments_grammar(json.loads(sys.argv[3]))\n"
        "sys.stdout.write(grammar)\n"
    )
    return subprocess.run(
        [str(ENGINE_PYTHON), "-c", script, str(ENGINE_SERVER),
         str(ENGINE_SERVER / "tool_schema.py"), json.dumps(schema)],
        capture_output=True, text=True, timeout=120,
    )


class SplashToolSchemaTests(unittest.TestCase):
    def test_root_anyof_is_relaxed_and_nested_schema_survives(self) -> None:
        schema, dropped = splash_runtime.compatible_tool_schema(browser_check_schema())
        self.assertIn("anyOf", dropped)
        self.assertNotIn("anyOf", schema)
        self.assertEqual(schema["required"], ["action"])
        self.assertIs(schema["additionalProperties"], False)
        # Nested uses stay: the engine only refuses the schema root.
        self.assertEqual(len(schema["properties"]["steps"]["items"]["anyOf"]), len(ACTIONS))
        self.assertEqual(schema["properties"]["action"]["enum"], ACTIONS + ["sequence"])

    def test_compatible_schema_is_returned_unchanged(self) -> None:
        original = {
            "type": "object",
            "properties": {"path": {"type": "string"}, "line": {"type": "integer"}},
            "required": ["path"],
        }
        schema, dropped = splash_runtime.compatible_tool_schema(original)
        self.assertEqual(dropped, [])
        self.assertEqual(schema, original)

    def test_required_names_without_properties_are_dropped(self) -> None:
        schema, dropped = splash_runtime.compatible_tool_schema({
            "type": "object", "properties": {"a": {"type": "string"}},
            "required": ["a", "missing"],
        })
        self.assertIn("required", dropped)
        self.assertEqual(schema["required"], ["a"])

    def test_non_object_root_type_is_dropped(self) -> None:
        schema, dropped = splash_runtime.compatible_tool_schema({"type": "string"})
        self.assertEqual(dropped, ["type"])
        self.assertEqual(schema, {})

    def test_relax_tool_schemas_covers_both_tool_shapes_in_place(self) -> None:
        chat_tool = {"type": "function", "function": {
            "name": "browser_check", "parameters": browser_check_schema(),
        }}
        response_tool = {"type": "function", "name": "browser_check",
                         "parameters": browser_check_schema()}
        plain_tool = {"type": "function", "name": "read", "parameters": {
            "type": "object", "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }}
        request = {"tools": [chat_tool, response_tool, plain_tool, "ignored"]}
        relaxed, keywords = splash_runtime.relax_tool_schemas(request)
        self.assertEqual(relaxed, 2)
        self.assertEqual(keywords, ("anyOf",))
        self.assertNotIn("anyOf", chat_tool["function"]["parameters"])
        self.assertNotIn("anyOf", response_tool["parameters"])
        self.assertEqual(plain_tool["parameters"]["required"], ["path"])

    def test_relay_applies_the_engine_subset_for_splash_only(self) -> None:
        body = json.dumps({
            "model": "incoai/Qwen3.8-27B-Splash",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"type": "function", "function": {
                "name": "browser_check", "parameters": browser_check_schema(),
            }}],
        }).encode()
        config = {
            "backend": "splash", "servedModel": "incoai/Qwen3.8-27B-Splash",
            "reasoning": "auto", "outputLimit": 4096,
        }
        relayed = json.loads(session_proxy.transform_chat_request(body, config, {"client": "pi"}))
        self.assertNotIn("anyOf", relayed["tools"][0]["function"]["parameters"])

        other = dict(config, backend="mtplx")
        untouched = json.loads(session_proxy.transform_chat_request(body, other, {"client": "pi"}))
        self.assertIn("anyOf", untouched["tools"][0]["function"]["parameters"])

    @unittest.skipUnless(
        ENGINE_PYTHON.is_file() and (ENGINE_SERVER / "tool_schema.py").is_file(),
        "Splash engine is not installed",
    )
    def test_installed_engine_rejects_then_accepts_the_real_schema(self) -> None:
        rejected = compile_with_engine(browser_check_schema())
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn(
            "unsupported top-level tool schema keyword(s): anyOf", rejected.stderr,
        )
        relaxed, _ = splash_runtime.compatible_tool_schema(browser_check_schema())
        accepted = compile_with_engine(relaxed)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertIn("parameter_", accepted.stdout)


if __name__ == "__main__":
    unittest.main()
