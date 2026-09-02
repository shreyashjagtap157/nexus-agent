import re

with open("tests/nexus_agent/cli/test_wizard.py", "r") as f:
    content = f.read()

patch_block = """
    def setUp(self):
        self.console = Console(force_terminal=False)
        self.prompt_mock = MagicMock()
        self.confirm_mock = MagicMock()
        self.patcher = patch("nexus_agent.cli.wizard.ModelManager")
        self.mock_model_manager = self.patcher.start()
        # Mock hardware detection to avoid subprocess timeouts in CI
        self.mock_model_manager.return_value.detect_hardware.return_value = {
            "cpu": "Mock CPU",
            "ram_gb": 16,
            "has_gpu": False,
            "has_npu": False,
            "npu_name": None,
            "vram_gb": 0,
            "gpu_name": None,
            "os": "Mock OS",
            "system": "Mock System"
        }

    def tearDown(self):
        self.patcher.stop()
"""

# Replace the setUp method
import re
content = re.sub(
    r'    def setUp\(self\):\n        self\.console = Console\(force_terminal=False\)\n        self\.prompt_mock = MagicMock\(\)\n        self\.confirm_mock = MagicMock\(\)\n',
    patch_block.strip() + '\n',
    content
)

with open("tests/nexus_agent/cli/test_wizard.py", "w") as f:
    f.write(content)
