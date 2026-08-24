"""Tests for the permission system."""

import pytest

from nexus_agent.permissions.manager import PermissionManager
from nexus_agent.permissions.rules import PermissionLevel, PermissionRule, DEFAULT_RULES


class TestPermissionLevel:
    def test_allow(self):
        assert PermissionLevel.ALLOW.value == "allow"

    def test_ask(self):
        assert PermissionLevel.ASK.value == "ask"

    def test_deny(self):
        assert PermissionLevel.DENY.value == "deny"

    def test_all_levels(self):
        levels = [l.value for l in PermissionLevel]
        assert set(levels) == {"allow", "ask", "deny"}


class TestPermissionRule:
    def test_rule_creation(self):
        rule = PermissionRule(
            tool_name="read_file",
            level=PermissionLevel.ALLOW,
            description="Reading files is safe",
        )
        assert rule.tool_name == "read_file"
        assert rule.level == PermissionLevel.ALLOW

    def test_rule_matches(self):
        rule = PermissionRule(
            tool_name="read_file",
            level=PermissionLevel.ALLOW,
        )
        assert rule.matches("read_file") is True
        assert rule.matches("write_file") is False

    def test_wildcard_rule(self):
        rule = PermissionRule(
            tool_name="*",
            level=PermissionLevel.ASK,
        )
        assert rule.matches("anything") is True
        assert rule.matches("read_file") is True

    def test_rule_with_arg_patterns(self):
        rule = PermissionRule(
            tool_name="shell",
            level=PermissionLevel.ASK,
            arg_patterns={"command": "^rm"},
        )
        assert rule.matches("shell", {"command": "rm -rf /"}) is True
        assert rule.matches("shell", {"command": "ls"}) is False

    def test_rule_serialization(self):
        rule = PermissionRule(
            tool_name="test",
            level=PermissionLevel.ALLOW,
            description="test rule",
        )
        d = rule.to_dict()
        assert d["tool_name"] == "test"
        assert d["level"] == "allow"

        restored = PermissionRule.from_dict(d)
        assert restored.tool_name == "test"
        assert restored.level == PermissionLevel.ALLOW

    def test_default_rules_exist(self):
        assert len(DEFAULT_RULES) > 0
        # Should have rules for common tools
        tool_names = {r.tool_name for r in DEFAULT_RULES}
        assert "read_file" in tool_names
        assert "write_file" in tool_names


class TestPermissionManager:
    @pytest.fixture
    def pm(self):
        return PermissionManager()

    def test_read_file_allowed(self, pm):
        level = pm.evaluate("read_file")
        assert level == PermissionLevel.ALLOW

    def test_write_file_ask(self, pm):
        level = pm.evaluate("write_file")
        assert level == PermissionLevel.ASK

    def test_run_command_ask(self, pm):
        level = pm.evaluate("run_command")
        assert level == PermissionLevel.ASK

    def test_unknown_tool_default(self, pm):
        level = pm.evaluate("unknown_tool")
        assert level == PermissionLevel.ASK  # default is ASK

    def test_custom_default_level(self):
        pm = PermissionManager(default_level=PermissionLevel.DENY)
        level = pm.evaluate("unknown_tool")
        assert level == PermissionLevel.DENY

    def test_always_allow(self, pm):
        pm.grant_always("shell")
        level = pm.evaluate("shell")
        assert level == PermissionLevel.ALLOW

    def test_revoke_always(self, pm):
        pm.grant_always("shell")
        pm.revoke_always("shell")
        level = pm.evaluate("shell")
        assert level == PermissionLevel.ASK

    def test_add_rule(self, pm):
        rule = PermissionRule(
            tool_name="custom_tool",
            level=PermissionLevel.ALLOW,
        )
        pm.add_rule(rule)
        level = pm.evaluate("custom_tool")
        assert level == PermissionLevel.ALLOW

    def test_remove_rule(self, pm):
        before = len(pm._rules)
        pm.add_rule(PermissionRule(
            tool_name="temp_tool",
            level=PermissionLevel.DENY,
        ))
        removed = pm.remove_rule("temp_tool")
        assert removed == 1

    def test_get_rules(self, pm):
        rules = pm.get_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_clear_session_state(self, pm):
        pm.grant_always("shell")
        pm.clear_session_state()
        level = pm.evaluate("shell")
        assert level != PermissionLevel.ALLOW

    def test_load_from_config(self, pm):
        config = {
            "permissions": {
                "mode": "auto",
                "tools": {
                    "read_file": "allow",
                    "write_file": "allow",
                },
            }
        }
        pm.load_from_config(config)
        assert pm.evaluate("read_file") == PermissionLevel.ALLOW
        assert pm.evaluate("write_file") == PermissionLevel.ALLOW

    def test_check_and_approve_allow(self, pm):
        assert pm.check_and_approve("read_file") is True

    def test_check_and_approve_deny(self, pm):
        pm.add_rule(PermissionRule(
            tool_name="dangerous_tool",
            level=PermissionLevel.DENY,
        ))
        assert pm.check_and_approve("dangerous_tool") is False

    def test_call_key_generation(self, pm):
        key1 = pm._make_call_key("tool", {"arg": "value"})
        key2 = pm._make_call_key("tool", {"arg": "value"})
        assert key1 == key2

        key3 = pm._make_call_key("tool", {"arg": "different"})
        assert key1 != key3
