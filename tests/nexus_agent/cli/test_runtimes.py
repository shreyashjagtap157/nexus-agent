"""Tests for runtimes.py — runtime detection, scanning, and formatting."""

import unittest
from unittest.mock import MagicMock, patch

from nexus_agent.cli.runtimes import (
    RuntimeInfo,
    _check_cpu,
    _check_cuda,
    _check_openvino,
    _check_rocm,
    _check_tpu,
    _check_vulkan,
    _validate_runtime_path,
    format_runtime_list,
    scan_runtimes,
)


class TestRuntimeInfo(unittest.TestCase):
    """Test the RuntimeInfo dataclass."""

    def test_defaults(self):
        rt = RuntimeInfo(name="test", provider="local", available=True)
        self.assertEqual(rt.name, "test")
        self.assertEqual(rt.provider, "local")
        self.assertTrue(rt.available)
        self.assertEqual(rt.path, "")
        self.assertEqual(rt.version, "")
        self.assertEqual(rt.description, "")
        self.assertEqual(rt.priority, 0)

    def test_with_all_fields(self):
        rt = RuntimeInfo(
            name="CUDA",
            provider="cuda",
            available=True,
            path="/usr/bin/nvcc",
            version="12.1",
            description="NVIDIA CUDA",
            priority=90,
        )
        self.assertEqual(rt.name, "CUDA")
        self.assertEqual(rt.provider, "cuda")
        self.assertEqual(rt.priority, 90)


class TestValidateRuntimePath(unittest.TestCase):
    """Test runtime path validation."""

    @patch("os.path.isfile", return_value=True)
    @patch("os.path.isdir", return_value=False)
    @patch("os.path.exists", return_value=True)
    def test_valid_file(self, mock_exists, mock_isdir, mock_isfile):
        self.assertTrue(_validate_runtime_path("/usr/bin/nvcc"))

    @patch("os.path.isfile", return_value=False)
    @patch("os.path.isdir", return_value=True)
    @patch("os.path.exists", return_value=True)
    def test_valid_directory(self, mock_exists, mock_isdir, mock_isfile):
        self.assertTrue(_validate_runtime_path("/usr/local/cuda"))

    @patch("os.path.isfile", return_value=False)
    @patch("os.path.isdir", return_value=False)
    @patch("os.path.exists", return_value=False)
    def test_non_existent(self, mock_exists, mock_isdir, mock_isfile):
        self.assertFalse(_validate_runtime_path("/usr/bin/missing"))


class TestCheckCpu(unittest.TestCase):
    """Test CPU runtime detection."""

    @patch("nexus_agent.cli.runtimes._which", return_value="/usr/bin/llama-cli")
    def test_detects_llama_cli(self, mock_which):
        runtimes = _check_cpu()
        names = [r.name for r in runtimes]
        self.assertIn("llama.cpp (CPU)", names)

    @patch("nexus_agent.cli.runtimes._which", return_value=None)
    @patch("nexus_agent.cli.runtimes.shutil.which", return_value=None)
    def test_always_has_cpu_default(self, mock_which, mock_shutil):
        runtimes = _check_cpu()
        names = [r.name for r in runtimes]
        self.assertIn("CPU (default)", names)

    @patch("nexus_agent.cli.runtimes._which", return_value=None)
    @patch("nexus_agent.cli.runtimes.shutil.which", return_value=None)
    def test_cpu_default_lowest_priority(self, mock_which, mock_shutil):
        runtimes = _check_cpu()
        self.assertEqual(runtimes[-1].name, "CPU (default)")
        self.assertEqual(runtimes[-1].priority, 10)

    @patch("nexus_agent.cli.runtimes._which", return_value=None)
    @patch("nexus_agent.cli.runtimes.shutil.which", return_value=None)
    def test_llama_cpp_python_imported(self, mock_which, mock_shutil):
        with patch.dict(
            "sys.modules", {"llama_cpp": MagicMock(__file__="/path/llama_cpp/__init__.py")}
        ):
            runtimes = _check_cpu()
            names = [r.name for r in runtimes]
            self.assertIn("llama-cpp-python", names)

    @patch("nexus_agent.cli.runtimes._which", return_value=None)
    @patch("nexus_agent.cli.runtimes.shutil.which", return_value=None)
    def test_transformers_imported(self, mock_which, mock_shutil):
        with patch.dict(
            "sys.modules", {"transformers": MagicMock(__file__="/path/transformers/__init__.py")}
        ):
            runtimes = _check_cpu()
            names = [r.name for r in runtimes]
            self.assertIn("HuggingFace Transformers", names)


class TestCheckCuda(unittest.TestCase):
    """Test CUDA runtime detection."""

    @patch("nexus_agent.cli.runtimes._which", return_value="/usr/bin/nvcc")
    @patch("nexus_agent.cli.runtimes._validate_runtime_path", return_value=True)
    @patch("subprocess.run")
    def test_nvcc_found(self, mock_run, mock_validate, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="nvcc: NVIDIA (R) Cuda compiler driver\nCopyright (c) 2005-2024 NVIDIA Corporation\nBuilt on Thu_Feb_15_19:55:08_PST_2024\nCuda compilation tools, release 12.1, V12.1.66\n",
        )
        runtimes = _check_cuda()
        names = [r.name for r in runtimes]
        self.assertIn("CUDA (nvcc compiler)", names)

    @patch("nexus_agent.cli.runtimes._which", return_value="/usr/bin/nvcc")
    @patch("nexus_agent.cli.runtimes._validate_runtime_path", return_value=True)
    @patch("subprocess.run")
    def test_nvcc_version_parsed(self, mock_run, mock_validate, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Cuda compilation tools, release 12.1, V12.1.66\n",
        )
        runtimes = _check_cuda()
        nvcc = [r for r in runtimes if "nvcc" in r.name][0]
        self.assertIn("12.1", nvcc.version)

    @patch(
        "nexus_agent.cli.runtimes._which",
        side_effect=lambda x: (
            "/usr/bin/llama-server" if x in ("llama-cli", "llama-server") else None
        ),
    )
    def test_llama_cuda_detected(self, mock_which):
        runtimes = _check_cuda()
        names = [r.name for r in runtimes]
        self.assertIn("llama.cpp (CUDA)", names)

    @patch("nexus_agent.cli.runtimes._which", return_value=None)
    def test_cuda_env_path(self, mock_which):
        with patch.dict("os.environ", {"CUDA_PATH": "/usr/local/cuda-12"}):
            runtimes = _check_cuda()
            names = [r.name for r in runtimes]
            self.assertIn("CUDA Toolkit", names)

    @patch("nexus_agent.cli.runtimes._which", return_value=None)
    def test_no_cuda(self, mock_which):
        with patch.dict("os.environ", {}, clear=True):
            runtimes = _check_cuda()
            self.assertEqual(len(runtimes), 0)


class TestCheckVulkan(unittest.TestCase):
    """Test Vulkan/DirectML runtime detection."""

    @patch("nexus_agent.cli.runtimes._which", return_value="/usr/bin/vulkaninfo")
    @patch("nexus_agent.cli.runtimes._validate_runtime_path", return_value=True)
    @patch("subprocess.run")
    def test_vulkan_found(self, mock_run, mock_validate, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="Vulkan Instance Version: 1.3.275\n")
        runtimes = _check_vulkan()
        names = [r.name for r in runtimes]
        self.assertIn("Vulkan", names)

    @patch("nexus_agent.cli.runtimes._which", return_value=None)
    @patch("nexus_agent.cli.runtimes.os.name", "nt")
    def test_no_vulkan(self, mock_which):

        # Safe way to mock sys.modules without blowing up dataclasses
        modules_patch = patch.dict(
            "sys.modules", {"onnxruntime": MagicMock(__file__="/path/onnxruntime/__init__.py")}
        )

        with patch.dict("os.environ", {}, clear=True), modules_patch:
            runtimes = _check_vulkan()
            names = [r.name for r in runtimes]
            self.assertIn("DirectML (NPU/GPU)", names)

    @patch(
        "nexus_agent.cli.runtimes._which",
        side_effect=lambda x: "/usr/bin/llama-vulkan" if x == "llama-vulkan" else None,
    )
    def test_llama_vulkan(self, mock_which):
        runtimes = _check_vulkan()
        names = [r.name for r in runtimes]
        self.assertIn("llama.cpp (Vulkan)", names)


class TestCheckRocm(unittest.TestCase):
    """Test ROCm runtime detection."""

    @patch("os.path.isdir", return_value=True)
    def test_rocm_env_path(self, mock_isdir):
        with patch.dict("os.environ", {"ROCM_PATH": "/opt/rocm"}):
            runtimes = _check_rocm()
            self.assertEqual(len(runtimes), 1)
            self.assertEqual(runtimes[0].name, "ROCm")

    def test_no_rocm(self):
        with patch.dict("os.environ", {}, clear=True):
            runtimes = _check_rocm()
            self.assertEqual(len(runtimes), 0)


class TestCheckOpenvino(unittest.TestCase):
    """Test OpenVINO runtime detection."""

    def test_openvino_imported(self):
        with patch.dict(
            "sys.modules", {"openvino": MagicMock(__file__="/path/openvino/__init__.py")}
        ):
            runtimes = _check_openvino()
            self.assertEqual(len(runtimes), 1)
            self.assertEqual(runtimes[0].provider, "openvino")

    def test_no_openvino(self):
        with patch.dict("sys.modules", {}, clear=True):
            runtimes = _check_openvino()
            self.assertEqual(len(runtimes), 0)


class TestCheckTpu(unittest.TestCase):
    """Test JAX/TPU runtime detection."""

    def test_jax_imported(self):
        with patch.dict("sys.modules", {"jax": MagicMock(__file__="/path/jax/__init__.py")}):
            runtimes = _check_tpu()
            self.assertEqual(len(runtimes), 1)
            self.assertEqual(runtimes[0].name, "JAX (TPU/GPU)")

    def test_no_jax(self):
        with patch.dict("sys.modules", {}, clear=True):
            runtimes = _check_tpu()
            self.assertEqual(len(runtimes), 0)


class TestScanRuntimes(unittest.TestCase):
    """Test the full scan_runtimes function."""

    @patch("nexus_agent.cli.runtimes._check_cpu")
    @patch("nexus_agent.cli.runtimes._check_cuda")
    @patch("nexus_agent.cli.runtimes._check_vulkan")
    @patch("nexus_agent.cli.runtimes._check_rocm")
    @patch("nexus_agent.cli.runtimes._check_openvino")
    @patch("nexus_agent.cli.runtimes._check_tpu")
    @patch("nexus_agent.cli.runtimes._check_vllm")
    @patch("nexus_agent.cli.runtimes._check_sglang")
    @patch("nexus_agent.cli.runtimes._check_mlx")
    @patch("nexus_agent.cli.runtimes._check_external_servers")
    @patch("nexus_agent.cli.runtimes._check_tensorrt")
    def test_all_checkers_called(
        self,
        mock_trt,
        mock_ext,
        mock_mlx,
        mock_sglang,
        mock_vllm,
        mock_tpu,
        mock_openvino,
        mock_rocm,
        mock_vulkan,
        mock_cuda,
        mock_cpu,
    ):
        mock_cpu.return_value = [
            RuntimeInfo(name="CPU", provider="local", available=True, priority=10)
        ]
        mock_cuda.return_value = [
            RuntimeInfo(name="CUDA", provider="cuda", available=True, priority=90)
        ]
        mock_vulkan.return_value = [
            RuntimeInfo(name="Vulkan", provider="vulkan", available=True, priority=70)
        ]
        mock_rocm.return_value = [
            RuntimeInfo(name="ROCm", provider="rocm", available=True, priority=65)
        ]
        mock_openvino.return_value = [
            RuntimeInfo(name="OpenVINO", provider="openvino", available=True, priority=45)
        ]
        mock_tpu.return_value = [
            RuntimeInfo(name="TPU", provider="tpu", available=True, priority=35)
        ]
        mock_vllm.return_value = []
        mock_sglang.return_value = []
        mock_mlx.return_value = []
        mock_ext.return_value = []
        mock_trt.return_value = []

        runtimes = scan_runtimes()
        self.assertEqual(len(runtimes), 6)
        self.assertEqual(runtimes[0].name, "CUDA")
        self.assertEqual(runtimes[-1].name, "CPU")

    def test_scan_runtimes_smoke(self):
        """scan_runtimes should never crash regardless of system state."""
        runtimes = scan_runtimes()
        self.assertIsInstance(runtimes, list)
        self.assertGreater(len(runtimes), 0)  # At least CPU default
        for rt in runtimes:
            self.assertIsInstance(rt, RuntimeInfo)
            self.assertTrue(rt.name)
            self.assertTrue(rt.provider)
            self.assertIsInstance(rt.available, bool)
            self.assertIsInstance(rt.priority, int)


class TestFormatRuntimeList(unittest.TestCase):
    """Test runtime list formatting."""

    def test_format_multiple(self):
        runtimes = [
            RuntimeInfo(
                name="CUDA",
                provider="cuda",
                available=True,
                path="/usr/bin/nvcc",
                version="12.1",
                description="NVIDIA CUDA",
                priority=90,
            ),
            RuntimeInfo(
                name="CPU", provider="local", available=True, description="Default CPU", priority=10
            ),
        ]
        result = format_runtime_list(runtimes)
        self.assertIn("CUDA", result)
        self.assertIn("CPU", result)
        self.assertIn("12.1", result)
        self.assertIn("/usr/bin/nvcc", result)

    def test_format_empty(self):
        result = format_runtime_list([])
        self.assertIn("No runtimes detected", result)

    def test_format_single_builtin(self):
        runtimes = [
            RuntimeInfo(
                name="CPU (default)", provider="local", available=True, path="builtin", priority=10
            ),
        ]
        result = format_runtime_list(runtimes)
        self.assertIn("CPU (default)", result)
        self.assertNotIn("builtin", result)  # builtin path is not displayed


if __name__ == "__main__":
    unittest.main()
