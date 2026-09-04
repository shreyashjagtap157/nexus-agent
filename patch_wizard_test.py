with open("tests/nexus_agent/cli/test_wizard.py", "r") as f:
    content = f.read()

import_sys = "import sys\nfrom unittest.mock import MagicMock, patch"
new_content = content.replace("from unittest.mock import MagicMock, patch", import_sys)

patch_dec = '    @patch("nexus_agent.llm.model_manager.ModelManager.detect_hardware", return_value={"cpu": "Mock CPU", "cpu_threads": 4, "ram_total": "16 GB", "ram_available": "8 GB", "gpu": "Mock GPU", "vram": "8 GB"})\n    def test_'
new_content = new_content.replace('    def test_wizard_cloud_provider_configuration', patch_dec + 'wizard_cloud_provider_configuration')

with open("tests/nexus_agent/cli/test_wizard.py", "w") as f:
    f.write(new_content)
