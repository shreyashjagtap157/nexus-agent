"""Tests for new rendering features: ResourceMonitor, Token glyphs, and Diff tracking."""

import unittest
from unittest.mock import MagicMock, patch
from nexus_agent.cli.renderer import TokenUsage, PerRequest
from nexus_agent.cli.resource_monitor import ResourceMonitor, ResourceSnapshot, format_resource_line

class TestPerRequestRendering(unittest.TestCase):
    def test_glyph_display(self):
        req = PerRequest()
        req.input_tokens = 1000
        req.output_tokens = 500
        req.lines_added = 10
        req.lines_removed = 2
        req.elapsed = 4.2

        display = req.display()
        # Strip ANSI colors for comparison
        import re
        plain = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', display)
        self.assertIn("↓1,000", plain)
        self.assertIn("↑500", plain)
        self.assertIn("+10", plain)
        self.assertIn("-2", plain)
        self.assertIn("· 4.2s", plain)

    def test_empty_display(self):
        req = PerRequest()
        self.assertEqual(req.display(), "")

class TestTokenUsageGlyphs(unittest.TestCase):
    def test_display_short_glyphs(self):
        tu = TokenUsage()
        tu.total_input = 1000
        tu.total_output = 500
        # Expected: ↓1,000|↑500
        self.assertEqual(tu.display_short(), "↓1,000|↑500")

    def test_detail_str_glyphs(self):
        tu = TokenUsage()
        tu.last_request.input_tokens = 100
        tu.last_request.output_tokens = 50
        detail = tu.detail_str()
        self.assertIn("↓100", detail)
        self.assertIn("↑50", detail)

class TestResourceMonitor(unittest.TestCase):
    def setUp(self):
        self.mon = ResourceMonitor.get()
        self.mon.stop() # Reset state

    def test_subscription_lifecycle(self):
        # Initially inactive
        self.assertFalse(self.mon.is_active())

        # Subscribe
        self.mon.subscribe()
        self.assertTrue(self.mon.is_active())

        # Unsubscribe
        self.mon.unsubscribe()
        self.assertFalse(self.mon.is_active())

    def test_snapshot_defaults(self):
        snap = self.mon.snapshot()
        self.assertIsInstance(snap, ResourceSnapshot)
        self.assertGreaterEqual(snap.cpu_threads, 0)

    def test_format_resource_line(self):
        snap = ResourceSnapshot(
            cpu_percent=15.5,
            cpu_threads=8,
            ram_used_gb=4.2,
            ram_total_gb=16.0,
            gpu_percent=40,
            vram_used_gb=2.1,
            vram_total_gb=8.0
        )
        line = format_resource_line(snap)
        self.assertIn("CPU 16%", line)
        self.assertIn("RAM 4.2G/16G", line)
        self.assertIn("GPU 40%", line)
        self.assertIn("VRAM 2.1G/8G", line)

class TestDiffAccumulation(unittest.TestCase):
    def test_add_diff(self):
        req = PerRequest()
        req.add_diff(10, 5)
        req.add_diff(2, 1)
        self.assertEqual(req.lines_added, 12)
        self.assertEqual(req.lines_removed, 6)
