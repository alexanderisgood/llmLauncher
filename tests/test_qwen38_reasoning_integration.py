"""Opt-in installed-engine checks; tokenizer only, no model weights loaded.

Set LLM_LAUNCHER_QWEN38_MODEL to the actual 6-bit model directory and
LLM_LAUNCHER_REASONING_ENGINE to omlx or mtplx. Run with that engine's Python.
For omlx, LLM_LAUNCHER_OMLX_MODEL_SETTINGS can point at the launcher's generated
model_settings.json to check the exact settings used by the live session.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest


@unittest.skipUnless(os.environ.get("LLM_LAUNCHER_QWEN38_MODEL"),
                     "opt-in installed Qwen3.8 6-bit check")
class Qwen38ReasoningIntegrationTests(unittest.TestCase):
    def test_prior_reasoning_and_prompt_prefix_survive_followup(self):
        from transformers import AutoTokenizer

        path = Path(os.environ["LLM_LAUNCHER_QWEN38_MODEL"])
        config = json.loads((path / "config.json").read_text())
        self.assertEqual(config["quantization"]["bits"], 6)
        tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        marker = "PREVIOUS_REASONING_MUST_SURVIVE_73921"
        history = [
            {"role": "user", "content": "Remember the project decision."},
            {"role": "assistant", "content": "Decision recorded.",
             "reasoning_content": marker},
        ]
        followup = history + [{"role": "user", "content": "Continue the project."}]
        engine = os.environ["LLM_LAUNCHER_REASONING_ENGINE"]
        if engine == "omlx":
            from omlx.api.openai_models import Message
            from omlx.api.utils import extract_text_content, uses_native_reasoning_content
            from omlx.model_settings import ModelSettings, merge_chat_template_request_kwargs
            from omlx.model_discovery import detect_preserve_thinking

            settings_path = os.environ.get("LLM_LAUNCHER_OMLX_MODEL_SETTINGS")
            if settings_path:
                models = json.loads(Path(settings_path).read_text())["models"]
                self.assertEqual(len(models), 1)
                settings = ModelSettings(**next(iter(models.values())))
            else:
                settings = ModelSettings(preserve_thinking=True)
            kwargs = merge_chat_template_request_kwargs(settings)
            self.assertIs(kwargs["preserve_thinking"], True)
            native = uses_native_reasoning_content(
                path.name, config_model_type=config["model_type"],
                preserve_thinking_default=detect_preserve_thinking(path))
            self.assertTrue(native)

            def render(messages):
                extracted = extract_text_content(
                    [Message(**m) for m in messages], tokenizer=tokenizer,
                    native_reasoning_content=native, consolidate_system_messages=False,
                )
                return tokenizer.apply_chat_template(
                    extracted, tokenize=False, add_generation_prompt=False, **kwargs)

        elif engine == "mtplx":
            from mtplx.server import openai as server
            from mtplx.backends.descriptors import QWEN3_NEXT_DESCRIPTOR

            state = SimpleNamespace(
                args=SimpleNamespace(model=str(path), preserve_thinking="auto",
                                     strip_assistant_reasoning_history=False),
                backend_descriptor=QWEN3_NEXT_DESCRIPTOR,
                reasoning_history_scoped_capable=server._template_supports_scoped_reasoning(tokenizer),
            )
            self.assertEqual(server._model_family_for_state(state), "qwen3_8")
            self.assertEqual(server._reasoning_history_mode(state), "preserve")
            self.assertTrue(server._reasoning_history_preserve_echo_active(state))

            def render(messages):
                ids = server._encode_messages_uncached(
                    tokenizer, [server.ChatMessage(**m) for m in messages],
                    enable_thinking=True, preserve_reasoning_history=True,
                    add_generation_prompt=False,
                )
                return tokenizer.decode(ids)

        else:
            self.fail("Unknown test engine")

        prefix, continued = render(history), render(followup)
        self.assertIn(marker, prefix)
        self.assertIn(marker, continued)
        self.assertTrue(continued.startswith(prefix), "Earlier prompt prefix changed")
        stripped = tokenizer.apply_chat_template(
            followup, tokenize=False, add_generation_prompt=False,
            enable_thinking=True, preserve_thinking=False,
        )
        self.assertNotIn(marker, stripped, "Negative control must detect disabled preservation")


if __name__ == "__main__":
    unittest.main()
