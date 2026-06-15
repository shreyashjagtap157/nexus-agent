"""Tests for the permissions module — PermissionManager, PermissionRule, PermissionLevel."""

import unittest
from unittest.mock import MagicMock

from nexus_agent.permissions.manager import PermissionManager
from nexus_agent.permissions.rules import DEFAULT_RULES, PermissionLevel, PermissionRule


class TestPermissionLevel(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(PermissionLevel.ALLOW.value, "allow")
        self.assertEqual(PermissionLevel.ASK.value, "ask")
        self.assertEqual(PermissionLevel.DENY.value, "deny")


class TestPermissionRule(unittest.TestCase):
    def test_match_tool_name_exact(self):
        rule = PermissionRule(tool_name="read_file", level=PermissionLevel.ALLOW)
        self.assertTrue(rule.matches("read_file", {}))
        self.assertFalse(rule.matches("write_file", {}))

    def test_match_wildcard(self):
        rule = PermissionRule(tool_name="*", level=PermissionLevel.ALLOW)
        self.assertTrue(rule.matches("any_tool", {}))
        self.assertTrue(rule.matches("shell", {}))

    def test_match_regex_args(self):
        rule = PermissionRule(
            tool_name="shell",
            level=PermissionLevel.DENY,
            arg_patterns={"command": r"rm\s+-rf"},
        )
        self.assertTrue(rule.matches("shell", {"command": "rm -rf /"}))
        self.assertFalse(rule.matches("shell", {"command": "ls -la"}))

    def test_to_dict_roundtrip(self):
        rule = PermissionRule(
            tool_name="test",
            level=PermissionLevel.ASK,
            description="testing",
            arg_patterns={"path": r"\.env"},
        )
        d = rule.to_dict()
        restored = PermissionRule.from_dict(d)
        self.assertEqual(restored.tool_name, "test")
        self.assertEqual(restored.level, PermissionLevel.ASK)
        self.assertEqual(restored.arg_patterns["path"], r"\.env")


class TestDefaultRules(unittest.TestCase):
    def test_default_rules_exist(self):
        self.assertGreater(len(DEFAULT_RULES), 0)
        read_rules = [r for r in DEFAULT_RULES if r.level == PermissionLevel.ALLOW]
        self.assertGreater(len(read_rules), 0)


class TestPermissionManager(unittest.TestCase):
    def setUp(self):
        self.mgr = PermissionManager()

    def test_evaluate_allow(self):
        self.mgr.add_rule(PermissionRule(tool_name="read_file", level=PermissionLevel.ALLOW))
        result = self.mgr.evaluate("read_file", {})
        self.assertEqual(result, PermissionLevel.ALLOW)

    def test_evaluate_deny(self):
        self.mgr.add_rule(PermissionRule(tool_name="dangerous_op", level=PermissionLevel.DENY))
        result = self.mgr.evaluate("dangerous_op", {})
        self.assertEqual(result, PermissionLevel.DENY)

    def test_grant_always(self):
        self.mgr.grant_always("shell")
        result = self.mgr.evaluate("shell", {})
        self.assertEqual(result, PermissionLevel.ALLOW)

    def test_revoke_always(self):
        self.mgr.grant_always("shell")
        self.mgr.revoke_always("shell")
        result = self.mgr.evaluate("shell", {})
        self.assertNotEqual(result, PermissionLevel.ALLOW)

    def test_check_and_approve_allow(self):
        self.mgr.add_rule(PermissionRule(tool_name="safe_op", level=PermissionLevel.ALLOW))
        self.assertTrue(self.mgr.check_and_approve("safe_op", {}, "safe operation"))

    def test_check_and_approve_ask_approved(self):
        callback = MagicMock(return_value=True)
        self.mgr = PermissionManager(approval_callback=callback, default_level=PermissionLevel.ASK)
        self.mgr.add_rule(PermissionRule(tool_name="ask_op", level=PermissionLevel.ASK))
        self.assertTrue(self.mgr.check_and_approve("ask_op", {}, "needs approval"))
        callback.assert_called_once()

    def test_check_and_approve_ask_denied(self):
        callback = MagicMock(return_value=False)
        self.mgr = PermissionManager(approval_callback=callback, default_level=PermissionLevel.ASK)
        self.mgr.add_rule(PermissionRule(tool_name="ask_op", level=PermissionLevel.ASK))
        self.assertFalse(self.mgr.check_and_approve("ask_op", {}, "denied"))

    def test_add_and_remove_rule(self):
        rule = PermissionRule(tool_name="custom_tool", level=PermissionLevel.DENY)
        self.mgr.add_rule(rule)
        result = self.mgr.evaluate("custom_tool", {})
        self.assertEqual(result, PermissionLevel.DENY)
        removed = self.mgr.remove_rule("custom_tool")
        self.assertGreaterEqual(removed, 1)

    def test_get_rules(self):
        rules = self.mgr.get_rules()
        self.assertIsInstance(rules, list)

    def test_load_from_config(self):
        config = {
            "permissions": {
                "mode": "allow",
                "tools": {
                    "read_file": {"mode": "allow"},
                }
            }
        }
        self.mgr.load_from_config(config)
        self.assertEqual(self.mgr.evaluate("read_file", {}), PermissionLevel.ALLOW)

    def test_clear_session_state(self):
        self.mgr.grant_always("temp_tool")
        self.mgr.clear_session_state()
        result = self.mgr.evaluate("temp_tool", {})
        self.assertNotEqual(result, PermissionLevel.ALLOW)

    def test_make_call_key(self):
        key = PermissionManager._make_call_key("test", {"a": 1})
        self.assertTrue(key.startswith("test|"))
