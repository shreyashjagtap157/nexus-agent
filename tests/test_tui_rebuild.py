"""Tests for TUI rebuild features: ASCII status dashboard, git ΔLines, /unload, and /tools."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from nexus_agent.cli.renderer import NexusTerminalRenderer, TokenUsage, Verbosity
from nexus_agent.cli.app import NexusApp
from nexus_agent.core.agent import AgentLoop, AgentLoopConfig, AgentMode


class TestTuiRebuildFeatures(unittest.TestCase):
    def setUp(self):
        self.renderer = NexusTerminalRenderer(Verbosity.NORMAL)
        self.tokens = TokenUsage()
        self.tokens.total_input = 120
        self.tokens.total_output = 80
        self.tokens.context_window = 8192
        self.metrics = {"threads": 4}

    def test_welcome_dashboard_rendering_wide(self):
        """Assert that the dashboard renders correctly on a normal (wide) screen."""
        stdout_mock = MagicMock()
        with patch("sys.stdout.write", stdout_mock), \
             patch("shutil.get_terminal_size", return_value=MagicMock(columns=80, lines=24)), \
             patch("psutil.cpu_percent", return_value=12.5), \
             patch("psutil.virtual_memory", return_value=MagicMock(used=4*1024**3, total=16*1024**3)), \
             patch("subprocess.run") as mock_run:
            
            # Mock nvidia-smi and git diff
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="35\n"),  # GPU %
                MagicMock(returncode=0, stdout="12\t5\tfile1.py\n2\t1\tfile2.py\n")  # Git diff
            ]

            self.renderer.welcome(
                model_name="Llama-3-8B-Q4",
                workspace="/mock/workspace",
                version="1.0.0",
                provider="local",
                context_size=8192,
                tokens=self.tokens,
                metrics=self.metrics,
                active_agents=2
            )

            # Retrieve the calls to sys.stdout.write
            written_data = "".join(call[0][0] for call in stdout_mock.call_args_list)

            # Ensure model name, CPU/GPU stats, RAM stats, token IO, context, git diff and processes are present
            self.assertIn("Llama-3-8B-Q4", written_data)
            self.assertIn("Mem: 4.0G/16G", written_data)
            self.assertIn("CPU: 4 threads", written_data)
            self.assertIn("GPU: 35%", written_data)
            self.assertIn("Context: 200/8192", written_data)
            self.assertIn("Tokens In: 120", written_data)
            self.assertIn("Out: 80", written_data)
            self.assertIn("ΔLines: +14/-6", written_data)
            self.assertIn("Processes (agents): 2", written_data)

    def test_welcome_dashboard_rendering_narrow(self):
        """Assert that the dashboard scales down to 55 cols on a narrow screen."""
        stdout_mock = MagicMock()
        with patch("sys.stdout.write", stdout_mock), \
             patch("shutil.get_terminal_size", return_value=MagicMock(columns=60, lines=24)), \
             patch("psutil.cpu_percent", return_value=5.0), \
             patch("psutil.virtual_memory", return_value=MagicMock(used=2*1024**3, total=8*1024**3)), \
             patch("subprocess.run") as mock_run:
            
            mock_run.side_effect = [
                MagicMock(returncode=1),  # GPU query fails/not available
                MagicMock(returncode=0, stdout="0\t0\tfile.py\n")
            ]

            self.renderer.welcome(
                model_name="Nemotron-4B",
                workspace="/mock/workspace",
                version="1.0.0",
                provider="local",
                context_size=4096,
                tokens=self.tokens,
                metrics=self.metrics,
                active_agents=0
            )

            written_data = "".join(call[0][0] for call in stdout_mock.call_args_list)

            self.assertIn("Nemotron-4B", written_data)
            self.assertIn("GPU: 0%", written_data)
            self.assertIn("ΔLines: +0/-0", written_data)
            self.assertIn("Processes (agents): 0", written_data)
            
            # Confirm box dimensions: lines should start with ┌ and have 55 ─ characters
            self.assertIn("┌" + "─" * 55 + "┐", written_data)

    def test_tools_command_cli_action(self):
        """Verify the CLI invocation of the /tools command enables/disables tools."""
        # Create a mock agent loop with some mock tools
        mock_tool_1 = MagicMock()
        mock_tool_1.name = "read_file"
        mock_tool_1.description = "Read a file"
        
        mock_tool_2 = MagicMock()
        mock_tool_2.name = "write_file"
        mock_tool_2.description = "Write a file"

        mock_agent = MagicMock()
        mock_agent.tools = [mock_tool_1, mock_tool_2]
        mock_agent.disabled_tools = set()

        app = NexusApp(quiet=True)
        app._agent = mock_agent

        # Call disable
        app._cmd_tools("disable read_file")
        self.assertIn("read_file", mock_agent.disabled_tools)

        # Call enable
        app._cmd_tools("enable read_file")
        self.assertNotIn("read_file", mock_agent.disabled_tools)

        # Call toggle
        app._cmd_tools("toggle write_file")
        self.assertIn("write_file", mock_agent.disabled_tools)
        app._cmd_tools("toggle write_file")
        self.assertNotIn("write_file", mock_agent.disabled_tools)

    def test_tools_command_interactive_menu(self):
        """Verify interactive tool toggling using the terminal menu selection."""
        mock_tool = MagicMock()
        mock_tool.name = "shell"
        mock_tool.description = "Run shell commands"

        mock_agent = MagicMock()
        mock_agent.tools = [mock_tool]
        mock_agent.disabled_tools = set()

        app = NexusApp(quiet=True)
        app._agent = mock_agent

        # Mock _interactive_menu to simulate selecting "shell" and then exiting
        with patch.object(app, "_interactive_menu", side_effect=["shell", "exit"]):
            app._cmd_tools("")

        self.assertIn("shell", mock_agent.disabled_tools)

    def test_unload_commands(self):
        """Verify /unload and /model unload explicitly release engine resources."""
        app = NexusApp(quiet=True)
        mock_engine = MagicMock()
        app._engine = mock_engine
        mock_agent = MagicMock()
        app._agent = mock_agent

        # Call unload via direct /unload handler
        app._cmd_unload("")
        
        # Verify engine.unload() was called, and references cleared
        mock_engine.unload.assert_called_once()
        self.assertIsNone(app._engine)
        self.assertIsNone(app._agent)
        self.assertEqual(app._model_status, "idle")

    def test_model_unload_subcommand(self):
        """Verify /model unload clears the model state and engine."""
        app = NexusApp(quiet=True)
        mock_engine = MagicMock()
        app._engine = mock_engine
        mock_agent = MagicMock()
        app._agent = mock_agent

        app._cmd_model("unload")
        
        mock_engine.unload.assert_called_once()
        self.assertIsNone(app._engine)
        self.assertIsNone(app._agent)
        self.assertEqual(app._model_status, "idle")

    def test_model_switch_with_spaces(self):
        """Verify switching to a model whose name contains spaces parses correctly."""
        app = NexusApp(quiet=True)
        mock_db = MagicMock()
        mock_db.get_path.return_value = "/mock/model.gguf"
        app._models_db = mock_db

        with patch("os.path.isfile", return_value=True), \
             patch.object(app, "_init_engine"), \
             patch.object(app, "_init_agent"):
            # Command with unquoted spaces
            app._cmd_model("switch Nemotron 3 Nano 4B")
            mock_db.get_path.assert_called_with("Nemotron 3 Nano 4B")
            self.assertEqual(app._model_path, "/mock/model.gguf")

            # Command with quoted name
            mock_db.reset_mock()
            app._cmd_model("switch \"Nemotron 3 Nano 4B\"")
            mock_db.get_path.assert_called_with("Nemotron 3 Nano 4B")

    def test_workspace_session_auto_resume(self):
        """Verify the session orchestrator resumes the last session by default unless new_session is True."""
        from pathlib import Path
        app = NexusApp(quiet=True, workspace=Path("/mock/workspace"))
        
        # Mock SessionManager
        mock_sess_mgr = MagicMock()
        mock_sess_mgr.get_last_session_for_workspace.return_value = "session-123"
        mock_sess_mgr.resume_session.return_value = {"mode": "auto"}
        app._session_mgr = mock_sess_mgr

        # Mock engine creation to avoid calling ProviderFactory
        app._engine = MagicMock()
        app._engine.model_name = "test-model"

        with patch("nexus_agent.cli.session_handler.MemoryManager"), \
             patch("nexus_agent.cli.session_handler.CheckpointManager"), \
             patch("nexus_agent.cli.session_handler.PermissionManager"), \
             patch("nexus_agent.cli.session_handler.ModelsDB"), \
             patch("nexus_agent.cli.session_handler.AuthStore"), \
             patch("nexus_agent.cli.session_handler.RuntimeManager"), \
             patch.object(app, "_init_mcp"), \
             patch.object(app, "_init_skills"), \
             patch.object(app, "_init_engine"):
            
            # Case 1: auto resume
            app._new_session = False
            app._session_id = None
            app._init_agent()
            expected_ws = str(Path("/mock/workspace"))
            mock_sess_mgr.get_last_session_for_workspace.assert_called_with(expected_ws)
            mock_sess_mgr.resume_session.assert_called_with("session-123")
            self.assertEqual(app._session_id, "session-123")

            # Case 2: new session (bypass resume)
            mock_sess_mgr.reset_mock()
            mock_sess_mgr.create_session.return_value = "session-new"
            app._new_session = True
            app._session_id = None
            app._init_agent()
            mock_sess_mgr.get_last_session_for_workspace.assert_not_called()
            mock_sess_mgr.create_session.assert_called()
            self.assertEqual(app._session_id, "session-new")

    def test_isolated_runtime_activation(self):
        """Verify activate_runtime prepends the correct path to sys.path and invalidates caches."""
        from nexus_agent.llm.runtime_manager import RuntimeManager
        
        test_backend = "test_cuda"
        data_dir_path = os.path.expanduser("~/.nexus-agent")
        expected_dir = os.path.abspath(os.path.join(data_dir_path, "runtimes", test_backend))

        # Ensure the test directory exists for activate_runtime to check it
        with patch("os.path.exists", return_value=True), \
             patch("importlib.invalidate_caches") as mock_invalidate:
            
            original_sys_path = list(sys.path)
            try:
                # Remove the directory if it's already in sys.path somehow
                if expected_dir in sys.path:
                    sys.path.remove(expected_dir)
                
                RuntimeManager.activate_runtime(test_backend)
                
                self.assertIn(expected_dir, sys.path)
                self.assertEqual(sys.path[0], expected_dir)
                mock_invalidate.assert_called_once()
            finally:
                if expected_dir in sys.path:
                    sys.path.remove(expected_dir)

    def test_custom_model_tuning_parameters(self):
        """Verify that model tuning parameters are validated and passed to LocalEngine constructor."""
        from nexus_agent.llm.runtime_manager import RuntimeManager
        
        config = {
            "local_model": {
                "runtime": "llama-cpp",
                "default_model": "/mock/model.gguf",
                "seed": 1337,
                "flash_attention": False,
                "unified_kv_cache": False,
                "rope_freq_base": 10000.0,
                "rope_freq_scale": 1.0,
                "kv_quant_type": "q8_0",
                "keep_in_memory": False,
                "use_agent_protocol": True,
                "reasoning_depth": 10,
            }
        }
        
        rm = RuntimeManager(config)
        self.assertEqual(rm._seed, 1337)
        self.assertEqual(rm._flash_attention, False)
        self.assertEqual(rm._unified_kv_cache, False)
        self.assertEqual(rm._rope_freq_base, 10000.0)
        self.assertEqual(rm._rope_freq_scale, 1.0)
        self.assertEqual(rm._kv_quant_type, "q8_0")
        self.assertEqual(rm._keep_in_memory, False)
        self.assertEqual(rm._use_agent_protocol, True)
        self.assertEqual(rm._reasoning_depth, 10)
        
        # Now mock LocalEngine constructor and verify the parameters are passed
        with patch("nexus_agent.llm.runtime_manager.LocalEngine") as mock_engine_cls, \
             patch("pathlib.Path.exists", return_value=True):
             
            rm.select_engine("/mock/model.gguf")
            mock_engine_cls.assert_called_once()
            kwargs = mock_engine_cls.call_args[1]
            
            self.assertEqual(kwargs["seed"], 1337)
            self.assertEqual(kwargs["flash_attention"], False)
            self.assertEqual(kwargs["unified_kv_cache"], False)
            self.assertEqual(kwargs["rope_freq_base"], 10000.0)
            self.assertEqual(kwargs["rope_freq_scale"], 1.0)
            self.assertEqual(kwargs["kv_quant_type"], "q8_0")
            self.assertEqual(kwargs["keep_in_memory"], False)
            self.assertEqual(kwargs["use_agent_protocol"], True)
            self.assertEqual(kwargs["reasoning_depth"], 10)

