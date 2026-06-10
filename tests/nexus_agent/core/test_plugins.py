"""Tests for PluginManager and plugin loading."""

from __future__ import annotations

import shutil
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from nexus_agent.core.plugins import NexusPlugin, PluginInfo, PluginManager


class _NexusPluginSubclass(NexusPlugin):
    def initialize(self) -> None:
        self.manager.register_command(
            self.name, "/testclass", lambda d, a: None
        )


class TestPlugins(unittest.TestCase):
    def setUp(self):
        self.tmpd = Path("tmp") / f"plugins_test_{uuid.uuid4().hex[:8]}"
        self.tmpd.mkdir(parents=True, exist_ok=True)
        self.pm = PluginManager(workspace=self.tmpd, plugin_dirs=[self.tmpd])

    def tearDown(self):
        # Unload loaded modules to keep sys.modules clean
        for k in list(sys.modules.keys()):
            if k.startswith("nexus_plugin_"):
                sys.modules.pop(k, None)
        shutil.rmtree(self.tmpd, ignore_errors=True)

    def test_empty_discover_no_dir(self):
        pm = PluginManager(workspace=self.tmpd, plugin_dirs=[self.tmpd / "nonexistent"])
        res = pm.discover_and_load()
        assert res == {}

    def test_load_plugin_file_with_register_function(self):
        plugin_src = """
def register_plugin(manager):
    manager.register_command("fn_plugin", "/fncmd", lambda d, a: None)
"""
        file_path = self.tmpd / "fn_plugin.py"
        file_path.write_text(plugin_src, encoding="utf-8")

        res = self.pm.discover_and_load()
        assert "fn_plugin" in res
        info = res["fn_plugin"]
        assert info.error is None
        assert "/fncmd" in info.commands

    def test_load_plugin_file_with_subclass(self):
        plugin_src = """
from nexus_agent.core.plugins import NexusPlugin

class SimplePlugin(NexusPlugin):
    def initialize(self) -> None:
        self.manager.register_command("sub_plugin", "/subcmd", lambda d, a: None)
        self.manager.register_tool("sub_plugin", "mock-tool-instance")
"""
        file_path = self.tmpd / "sub_plugin.py"
        file_path.write_text(plugin_src, encoding="utf-8")

        res = self.pm.discover_and_load()
        assert "sub_plugin" in res
        info = res["sub_plugin"]
        assert info.error is None
        assert "/subcmd" in info.commands
        assert "mock-tool-instance" in info.tools

    def test_load_plugin_ignores_private_files(self):
        plugin_src = "def register_plugin(m): pass"
        (self.tmpd / "_private.py").write_text(plugin_src)
        res = self.pm.discover_and_load()
        assert "_private" not in res

    def test_load_plugin_no_entry_point_sets_error(self):
        (self.tmpd / "no_entry.py").write_text("x = 42")
        res = self.pm.discover_and_load()
        assert "no_entry" in res
        assert "No entry point" in res["no_entry"].error

    def test_load_plugin_syntax_error_handles_gracefully(self):
        (self.tmpd / "bad_syntax.py").write_text("def register_plugin(m): \n  invalid syntax here {{{")
        res = self.pm.discover_and_load()
        assert "bad_syntax" in res
        assert res["bad_syntax"].error is not None

    def test_register_command_normalizes_slash(self):
        info = PluginInfo(name="test")
        self.pm.plugins["test"] = info
        self.pm.register_command("test", "no_slash", lambda d, a: None)
        assert "/no_slash" in info.commands

    def test_register_command_ignored_if_plugin_missing(self):
        self.pm.register_command("missing", "/cmd", lambda d, a: None)
        assert not self.pm.plugins

    def test_register_tool_ignored_if_plugin_missing(self):
        self.pm.register_tool("missing", "tool")
        assert not self.pm.plugins

    def test_entry_points_loading(self):
        # We'll mock the importlib.metadata / importlib_metadata entry_points
        mock_ep = MagicMock()
        mock_ep.name = "ep_plugin"

        # When ep.load() is called, return a module-like object with a register_plugin function
        mock_module = MagicMock()
        mock_ep.load.return_value = mock_module

        def fake_register(manager):
            manager.register_command("ep_plugin", "/epcmd", lambda d, a: None)

        mock_module.register_plugin = fake_register

        with patch("sys.version_info", (3, 11)):
            with patch("importlib.metadata.entry_points") as mock_eps:
                mock_eps.return_value = [mock_ep]
                res = self.pm.discover_and_load()

        assert "ep_plugin" in res
        assert "/epcmd" in res["ep_plugin"].commands

    def test_entry_points_subclass_loading(self):
        mock_ep = MagicMock()
        mock_ep.name = "ep_subclass_plugin"
        # Use a real ModuleType to avoid MagicMock __dir__ issues
        mock_module = types.ModuleType("mock_module")
        mock_module.MyEPPlugin = _NexusPluginSubclass
        mock_ep.load.return_value = mock_module

        with patch("nexus_agent.core.plugins.dir", return_value=["MyEPPlugin"]):
            with patch("sys.version_info", (3, 11)):
                with patch("importlib.metadata.entry_points") as mock_eps:
                    mock_eps.return_value = [mock_ep]
                    res = self.pm.discover_and_load()

        assert "ep_subclass_plugin" in res
        assert "/testclass" in res["ep_subclass_plugin"].commands

    def test_entry_points_loading_failure_handled_gracefully(self):
        mock_ep = MagicMock()
        mock_ep.name = "failed_ep"
        mock_ep.load.side_effect = RuntimeError("failed to load")

        with patch("sys.version_info", (3, 11)):
            with patch("importlib.metadata.entry_points") as mock_eps:
                mock_eps.return_value = [mock_ep]
                res = self.pm.discover_and_load()

        assert "failed_ep" in res
        assert "failed to load" in res["failed_ep"].error

    def test_fallback_entry_points_for_older_python(self):
        # Mock importlib_metadata to simulate how it returns entry points
        mock_ep = MagicMock()
        mock_ep.name = "legacy_ep"

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            with patch("sys.version_info", (3, 9)):
                res = self.pm.discover_and_load()

        assert "legacy_ep" in res
