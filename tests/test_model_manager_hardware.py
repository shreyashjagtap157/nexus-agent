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

    with (
        patch.object(model_manager.platform, "system", return_value="Windows"),
        patch.object(model_manager, "_ttl_get", return_value=None),
        patch("subprocess.run", side_effect=[FileNotFoundError(), timeout]),
    ):
        hardware = model_manager.ModelManager().detect_hardware()

    assert hardware["npu"] == "Not detected"
    assert "recommended_model_size" in hardware
