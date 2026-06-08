"""Tests for model benchmarking interface."""

import unittest
from unittest.mock import MagicMock, patch

from nexus_agent.llm.base import LLMProvider, ProviderCapabilities, LLMResponse
from nexus_agent.llm.local_engine.engine import LocalEngine
from nexus_agent.llm.onnx_engine import OnnxEngine
from nexus_agent.llm.local_engine.inference_mixin import InferenceMixin


class TestBenchmarkInterface(unittest.TestCase):
    def test_local_engine_has_benchmark(self):
        """LocalEngine should have a benchmark method via InferenceMixin."""
        self.assertTrue(hasattr(InferenceMixin, "benchmark"))
        self.assertTrue(callable(InferenceMixin.benchmark))

    def test_onnx_engine_has_benchmark(self):
        """OnnxEngine should have a benchmark method."""
        self.assertTrue(hasattr(OnnxEngine, "benchmark"))
        self.assertTrue(callable(OnnxEngine.benchmark))

    def test_benchmark_signature(self):
        """benchmark should accept prompt and iterations params."""
        import inspect
        sig = inspect.signature(InferenceMixin.benchmark)
        params = list(sig.parameters.keys())
        self.assertIn("prompt", params)
        self.assertIn("iterations", params)

    def test_benchmark_result_structure(self):
        """benchmark result dict should contain expected keys."""
        expected_keys = {
            "prompt", "prompt_tokens", "iterations",
            "latency_avg_s", "latency_min_s", "latency_max_s",
            "ttft_avg_s", "ttft_min_s",
            "tokens_per_sec_avg", "tokens_per_sec_max",
            "model",
        }
        mock_engine = MagicMock(spec=InferenceMixin)
        mock_engine._ensure_loaded = MagicMock()

        # Mock the _llm tokenize and create_chat_completion
        class MockLlama:
            def tokenize(self, text):
                return [1, 2, 3]
            def create_chat_completion(self, **kwargs):
                if kwargs.get("stream"):
                    yield {"choices": [{"delta": {"content": "Hello"}, "finish_reason": None}]}
                    yield {"choices": [{"delta": {"content": " world"}, "finish_reason": None}]}
                    yield {"choices": [{"delta": {"content": "!"}, "finish_reason": "stop"}]}
                else:
                    return {"choices": [{"message": {"content": "Hello world!"}}], "usage": {}}

        mixin = InferenceMixin()
        mixin._llm = MockLlama()
        mixin._model_name_str = "test-model"

        result = mixin.benchmark(prompt="test", iterations=3)
        self.assertIsInstance(result, dict)
        for key in expected_keys:
            self.assertIn(key, result, f"Missing key: {key}")
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(result["prompt"], "test")
        self.assertGreater(result["iterations"], 0)
        self.assertGreater(result["latency_avg_s"], 0)

    def test_benchmark_error_handling(self):
        """benchmark should handle all iterations failing."""
        mixin = InferenceMixin()

        class FailingLlama:
            def tokenize(self, text):
                return [1, 2]
            def create_chat_completion(self, **kwargs):
                raise RuntimeError("Model not loaded")

        mixin._llm = FailingLlama()
        mixin._model_name_str = "test-model"

        result = mixin.benchmark(prompt="test", iterations=2)
        self.assertIn("error", result)
        self.assertEqual(result["iterations_attempted"], 2)


class TestBenchmarkCliIntegration(unittest.TestCase):
    @patch("nexus_agent.cli.commands.model_mixin.ModelCommandsMixin")
    def test_benchmark_command_registered(self, MockMixin):
        from nexus_agent.cli.command_dispatcher import SLASH_COMMANDS
        names = [cmd["name"] for cmd in SLASH_COMMANDS]
        self.assertIn("/model benchmark", names)

    def test_benchmark_command_dispatch(self):
        from nexus_agent.cli.commands.model_mixin import ModelCommandsMixin
        self.assertTrue(hasattr(ModelCommandsMixin, "_cmd_model_benchmark"))
        self.assertTrue(callable(ModelCommandsMixin._cmd_model_benchmark))


if __name__ == "__main__":
    unittest.main()
