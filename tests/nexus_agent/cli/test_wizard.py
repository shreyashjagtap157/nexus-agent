"""Tests for the SetupWizard interactive CLI.

Verifies that the wizard correctly collects user input and saves the resulting
configuration updates.
"""

import unittest
from unittest.mock import MagicMock, patch

from rich.console import Console

from nexus_agent.cli.wizard import CLOUD_PROVIDERS, SetupWizard


class TestSetupWizard(unittest.TestCase):
    def setUp(self):
        self.console = Console(force_terminal=False)
        self.prompt_mock = MagicMock()
        self.confirm_mock = MagicMock()

    def test_wizard_collects_basic_settings(self):
        """Verify wizard collects permission, memory, and guardrail modes."""
        # Setup mock responses
        # prompt_func: Permission mode, Memory mode, Guardrail level
        self.prompt_mock.side_effect = ["suggest", "session", "strict"]
        # confirm_func: install runtime?, HF page, add cloud keys
        self.confirm_mock.side_effect = [False, False, False]

        with patch("nexus_agent.cli.wizard.save_user_config") as mock_save:
            wizard = SetupWizard(
                console=self.console,
                prompt_func=self.prompt_mock,
                confirm_func=self.confirm_mock
            )
            updates = wizard.run()

            # Check captured settings
            self.assertEqual(updates["permissions"]["mode"], "suggest")
            self.assertEqual(updates["memory"]["mode"], "session")
            self.assertEqual(updates["memory"]["enabled"], False)
            self.assertEqual(updates["local_model"]["guardrails"], "strict")

            # Verify save was called
            mock_save.assert_called_once_with(updates)

    def test_wizard_cloud_provider_configuration(self):
        """Verify wizard collects cloud API keys and sets active provider."""
        # prompt_func: Permission, Memory, Guardrail, OpenAI Key
        self.prompt_mock.side_effect = ["ask", "full", "balanced", "sk-test-openai"]

        # confirm_func:
        # 0. Install runtime? (False)
        # 1. Open HF page? (False)
        # 2. Add cloud keys? (True)
        # 3. Configure OpenAI? (True)
        # 4. Configure Anthropic? (False)
        # ... others False ...
        # 5. Make active? (True)
        confirm_responses = [False, False, True, True] + [False] * (len(CLOUD_PROVIDERS) - 1)
        # We need to handle the "Make active" prompt which happens after the loop if any were configured
        confirm_responses.append(True)

        self.confirm_mock.side_effect = confirm_responses

        with patch("nexus_agent.cli.wizard.save_user_config") as mock_save:
            wizard = SetupWizard(
                console=self.console,
                prompt_func=self.prompt_mock,
                confirm_func=self.confirm_mock
            )
            updates = wizard.run()

            # Check provider config
            self.assertEqual(updates["providers"]["openai"]["api_key"], "sk-test-openai")
            self.assertEqual(updates["providers"]["active"], "openai")

            mock_save.assert_called_once_with(updates)

    def test_hardware_detection_integration(self):
        """Verify wizard uses ModelManager for hardware detection."""
        self.prompt_mock.side_effect = ["auto", "full", "balanced"]
        self.confirm_mock.side_effect = [False, False, False]

        with patch("nexus_agent.llm.model_manager.ModelManager.detect_hardware") as mock_detect:
            mock_detect.return_value = {
                "cpu": "Intel",
                "cpu_threads": 8,
                "ram_total": "16 GB",
                "ram_available": "8 GB",
                "gpu": "NVIDIA RTX 3060",
                "vram": "12 GB",
                "npu": "Not detected",
                "recommended_model_size": "7B-13B",
                "ram_total_bytes": 16 * 1024**3,
                "vram_bytes": 12 * 1024**3,
            }

            with patch("nexus_agent.cli.wizard.save_user_config"):
                wizard = SetupWizard(
                    console=self.console,
                    prompt_func=self.prompt_mock,
                    confirm_func=self.confirm_mock
                )
                wizard.run()

                # Verify hardware detection was called
                mock_detect.assert_called_once()
                # Verify GPU layers was set to -1 because GPU was detected
                self.assertEqual(wizard.config_updates["local_model"]["gpu_layers"], -1)
