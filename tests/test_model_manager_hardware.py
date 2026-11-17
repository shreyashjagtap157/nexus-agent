from __future__ import annotations

import subprocess
from unittest.mock import patch

from nexus_agent.llm import model_manager


def test_windows_npu_probe_timeout_does_not_abort_hardware_detection() -> None:
    model_manager._TTL_CACHE.pop("detect_hardware", None)
    timeout = subprocess.TimeoutExpired(
        cmd=["powershell", "-NoProfile", "-Command", "Get-CimInstance"],
        timeout=5,
    )

    def fake_run(cmd, *args, **kwargs):  # noqa: ANN001, ANN202
        # On Windows the stdlib ``platform`` helpers internally shell out via
        # ``subprocess.check_output`` -> ``subprocess.run``. A positional
        # ``side_effect`` list would therefore be consumed out of order and the
        # intended NPU timeout would fire against the wrong call. Dispatch on
        # the command instead so the probe under test is deterministic on every
        # platform.
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "powershell":
            raise timeout
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "nvidia-smi":
            raise FileNotFoundError()
        # Any other stdlib probe (e.g. ``platform``'s ``cmd /c ver``) succeeds
        # with empty output so detection continues normally.
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with (
        patch.object(model_manager.platform, "system", return_value="Windows"),
        patch.object(model_manager.platform, "processor", return_value="TestCPU"),
        patch.object(model_manager.platform, "machine", return_value="AMD64"),
        patch.object(model_manager, "_ttl_get", return_value=None),
        patch("subprocess.run", side_effect=fake_run),
    ):
        hardware = model_manager.ModelManager().detect_hardware()

    assert hardware["npu"] == "Not detected"
    assert "recommended_model_size" in hardware
