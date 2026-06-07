"""Tests for the BrowserTool — URL validation, SSRF protection, and the new
configurable Playwright path / screenshot directory logic."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexus_agent.tools.browser import (
    BrowserConfig,
    BrowserTool,
    _resolve_browser_executable,
)


class TestBrowserConfig(unittest.TestCase):
    def test_from_env_no_vars(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("NEXUS_BROWSER_")}
        with patch.dict(os.environ, env, clear=True):
            cfg = BrowserConfig.from_env(Path("/tmp/ws"))
        self.assertIsNone(cfg.executable_path)
        self.assertIsNone(cfg.user_data_dir)
        self.assertEqual(cfg.screenshot_dir, Path("/tmp/ws/.nexus-agent/screenshots"))
        self.assertEqual(cfg.navigation_timeout_ms, 15000)

    def test_from_env_with_vars(self):
        env_patch = {
            "NEXUS_BROWSER_EXECUTABLE": "/usr/bin/chromium",
            "NEXUS_BROWSER_USER_DATA_DIR": "/tmp/profile",
            "NEXUS_BROWSER_SCREENSHOT_DIR": "/tmp/shots",
            "NEXUS_BROWSER_TIMEOUT_MS": "8000",
        }
        with patch.dict(os.environ, env_patch, clear=True):
            cfg = BrowserConfig.from_env(Path("/tmp/ws"))
        self.assertEqual(cfg.executable_path, "/usr/bin/chromium")
        self.assertEqual(cfg.user_data_dir, Path("/tmp/profile"))
        self.assertEqual(cfg.screenshot_dir, Path("/tmp/shots"))
        self.assertEqual(cfg.navigation_timeout_ms, 8000)

    def test_invalid_timeout_falls_back_to_default(self):
        with patch.dict(os.environ, {"NEXUS_BROWSER_TIMEOUT_MS": "not-a-number"}, clear=True):
            cfg = BrowserConfig.from_env(Path("/tmp"))
        self.assertEqual(cfg.navigation_timeout_ms, 15000)


class TestResolveBrowserExecutable(unittest.TestCase):
    def test_explicit_existing_path(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            path = f.name
        try:
            self.assertEqual(_resolve_browser_executable(path), path)
        finally:
            os.unlink(path)

    def test_nonexistent_path_falls_back_to_which(self):
        # Use a clearly bogus path; then shutil.which should return None for
        # the next attempt and the helper should return None overall.
        with patch("shutil.which", return_value=None):
            self.assertIsNone(_resolve_browser_executable("/does/not/exist/chrome"))

    def test_resolution_via_which(self):
        with patch("shutil.which", return_value="/usr/bin/chromium"):
            self.assertEqual(_resolve_browser_executable("chromium"), "/usr/bin/chromium")


class TestBrowserURLValidation(unittest.TestCase):
    """Test the SSRF / private-IP blocker."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)
        self.tool = BrowserTool(workspace=self.workspace)

    def tearDown(self):
        self.tool.close()
        self.tmpdir.cleanup()

    def test_file_scheme_blocked(self):
        err = self.tool._validate_url("file:///etc/passwd")
        self.assertIsNotNone(err)
        self.assertIn("file://", err)

    def test_unsupported_scheme_blocked(self):
        err = self.tool._validate_url("ftp://example.com/foo")
        self.assertIsNotNone(err)
        self.assertIn("scheme", err.lower())

    def test_metadata_ip_blocked(self):
        # 169.254.169.254 is cloud metadata — getaddrinfo should resolve it
        # but our blocklist catches it before httpx.
        err = self.tool._validate_url("http://169.254.169.254/latest/meta-data")
        self.assertIsNotNone(err)
        self.assertIn("metadata", err.lower())

    def test_loopback_blocked(self):
        err = self.tool._validate_url("http://127.0.0.1/admin")
        self.assertIsNotNone(err)
        self.assertIn("private", err.lower())

    def test_unresolvable_host(self):
        err = self.tool._validate_url("http://this-host-does-not-exist.invalid/")
        self.assertIsNotNone(err)


class TestBrowserToolConfigurable(unittest.TestCase):
    """Ensure the tool accepts a BrowserConfig and exposes the right env hooks."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_constructor_accepts_browserconfig(self):
        cfg = BrowserConfig(executable_path="/custom/chrome",
                             navigation_timeout_ms=5000)
        tool = BrowserTool(workspace=self.workspace, config=cfg)
        self.assertEqual(tool.config.executable_path, "/custom/chrome")
        self.assertEqual(tool.config.navigation_timeout_ms, 5000)
        tool.close()

    def test_default_user_data_dir_is_temp(self):
        tool = BrowserTool(workspace=self.workspace)
        self.assertTrue(tool.config.user_data_dir.exists())
        self.assertTrue(str(tool.config.user_data_dir).startswith(
            tempfile.gettempdir().rstrip("/\\")
        ) or "nexus_browser" in str(tool.config.user_data_dir))
        tool.close()

    def test_explicit_user_data_dir_preserved(self):
        profile = self.workspace / "browser_profile"
        cfg = BrowserConfig(user_data_dir=profile)
        tool = BrowserTool(workspace=self.workspace, config=cfg)
        self.assertEqual(tool.config.user_data_dir, profile)
        tool.close()

    def test_close_cleans_up_owned_temp_dir(self):
        tool = BrowserTool(workspace=self.workspace)
        temp_path = tool.config.user_data_dir
        tool.close()
        self.assertFalse(temp_path.exists())

    def test_close_does_not_delete_user_provided_dir(self):
        profile = self.workspace / "kept_profile"
        profile.mkdir()
        cfg = BrowserConfig(user_data_dir=profile)
        tool = BrowserTool(workspace=self.workspace, config=cfg)
        tool.close()
        # The user-provided dir should still exist (we only cleanup the auto-tempdir)
        self.assertTrue(profile.exists())


if __name__ == "__main__":
    unittest.main()
