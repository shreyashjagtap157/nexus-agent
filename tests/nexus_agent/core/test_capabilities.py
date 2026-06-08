"""Tests for hardware and model capability detection."""

import unittest
from unittest.mock import MagicMock, patch

from nexus_agent.core.capabilities import (
    HardwareCapabilities,
    ModelCapabilityProfile,
    detect_hardware,
    estimate_model_capabilities,
    get_recommended_runtime,
)


class TestHardwareCapabilities(unittest.TestCase):
    def test_detect_hardware_defaults(self):
        caps = detect_hardware()
        self.assertIsInstance(caps, HardwareCapabilities)
        self.assertGreater(caps.cpu_cores, 0)
        self.assertIsInstance(caps.has_cuda, bool)
        self.assertIsInstance(caps.is_windows, bool)

    def test_estimate_model_capabilities_cpu(self):
        hw = HardwareCapabilities(cpu_cores=8, ram_gb=16.0)
        profile = estimate_model_capabilities(hw, model_size_gb=4.0)
        self.assertFalse(profile.supports_vision)
        self.assertEqual(profile.max_context_length, 4096)
        self.assertGreater(profile.estimated_tokens_per_sec, 0)
        self.assertGreater(profile.max_model_size_gb, 0)

    def test_estimate_model_capabilities_cuda(self):
        hw = HardwareCapabilities(cpu_cores=8, ram_gb=32.0, has_cuda=True, vram_gb=12.0)
        profile = estimate_model_capabilities(hw, model_size_gb=7.0)
        self.assertTrue(profile.supports_tool_calling)
        self.assertGreater(profile.estimated_tokens_per_sec, 0)

    def test_estimate_model_capabilities_metal(self):
        hw = HardwareCapabilities(cpu_cores=8, ram_gb=16.0, has_metal=True, is_apple_silicon=True)
        profile = estimate_model_capabilities(hw, model_size_gb=3.0)
        self.assertTrue(profile.supports_tool_calling)
        self.assertEqual(profile.recommended_gpu_layers, -1)

    def test_estimate_model_capabilities_onnx(self):
        hw = HardwareCapabilities(cpu_cores=4, ram_gb=8.0)
        profile = estimate_model_capabilities(hw, model_size_gb=1.0, runtime_type="onnx")
        self.assertFalse(profile.supports_tool_calling)
        self.assertEqual(profile.recommended_batch_size, 256)

    def test_get_recommended_runtime_cuda(self):
        hw = HardwareCapabilities(has_cuda=True, vram_gb=8.0)
        self.assertEqual(get_recommended_runtime(hw), "cuda")

    def test_get_recommended_runtime_apple(self):
        hw = HardwareCapabilities(is_apple_silicon=True, ram_gb=16.0, has_metal=True)
        self.assertEqual(get_recommended_runtime(hw), "metal")

    def test_get_recommended_runtime_rocm(self):
        hw = HardwareCapabilities(has_rocm=True)
        self.assertEqual(get_recommended_runtime(hw), "rocm")

    def test_get_recommended_runtime_vulkan(self):
        hw = HardwareCapabilities(has_vulkan=True, is_windows=True)
        self.assertEqual(get_recommended_runtime(hw), "vulkan")

    def test_get_recommended_runtime_windows_onnx(self):
        hw = HardwareCapabilities(is_windows=True)
        self.assertEqual(get_recommended_runtime(hw), "onnx")

    def test_get_recommended_runtime_cpu_fallback(self):
        hw = HardwareCapabilities()
        self.assertEqual(get_recommended_runtime(hw), "cpu")

    def test_profile_batch_size_scaling(self):
        hw_low = HardwareCapabilities(ram_gb=8.0)
        hw_high = HardwareCapabilities(ram_gb=64.0)
        low_profile = estimate_model_capabilities(hw_low)
        high_profile = estimate_model_capabilities(hw_high)
        self.assertLess(low_profile.recommended_batch_size, high_profile.recommended_batch_size)

    def test_profile_external_server(self):
        hw = HardwareCapabilities(cpu_cores=4, ram_gb=8.0)
        profile = estimate_model_capabilities(hw, runtime_type="external_server")
        self.assertTrue(profile.supports_tool_calling)
        self.assertTrue(profile.supports_function_calling)

    def test_model_size_too_large(self):
        hw = HardwareCapabilities(ram_gb=8.0)
        profile = estimate_model_capabilities(hw, model_size_gb=100.0)
        self.assertLess(profile.estimated_tokens_per_sec, 10)
        self.assertLess(profile.max_model_size_gb, 15)


class TestModelCapabilityProfile(unittest.TestCase):
    def test_default_values(self):
        profile = ModelCapabilityProfile()
        self.assertFalse(profile.supports_tool_calling)
        self.assertFalse(profile.supports_vision)
        self.assertTrue(profile.supports_streaming)
        self.assertEqual(profile.max_context_length, 4096)
        self.assertEqual(profile.runtime_type, "llama_cpp")

    def test_custom_values(self):
        profile = ModelCapabilityProfile(
            supports_tool_calling=True,
            supports_vision=True,
            max_context_length=128000,
            runtime_type="external_server",
            estimated_tokens_per_sec=120.0,
        )
        self.assertTrue(profile.supports_tool_calling)
        self.assertTrue(profile.supports_vision)
        self.assertEqual(profile.max_context_length, 128000)
        self.assertEqual(profile.estimated_tokens_per_sec, 120.0)


if __name__ == "__main__":
    unittest.main()
