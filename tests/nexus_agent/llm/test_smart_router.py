"""Tests for SmartRouter provider failover and routing."""

import unittest
from unittest.mock import MagicMock, patch

from nexus_agent.llm.runtime_manager import SmartRouter
from nexus_agent.core.agent import AgentLoop, AgentLoopConfig


class TestSmartRouter(unittest.TestCase):
    def setUp(self):
        self.router = SmartRouter()

    def test_initial_response_times(self):
        self.assertIn("local", self.router._response_times)
        self.assertIn("openai", self.router._response_times)
        self.assertIn("anthropic", self.router._response_times)

    def test_update_latency_new_provider(self):
        self.router.update_latency("custom_provider", 0.5)
        self.assertIn("custom_provider", self.router._response_times)
        self.assertEqual(self.router._response_times["custom_provider"], 0.5)

    def test_update_latency_exponential_moving_average(self):
        self.router._response_times["test_prov"] = 1.0
        self.router.update_latency("test_prov", 0.5)
        expected = (0.7 * 1.0) + (0.3 * 0.5)
        self.assertAlmostEqual(self.router._response_times["test_prov"], expected)

    def test_select_provider_low_complexity(self):
        provider = self.router.select_provider("low")
        self.assertIn(provider, ["groq", "ollama", "local"])

    def test_select_provider_medium_complexity(self):
        provider = self.router.select_provider("medium")
        self.assertIn(provider, ["google", "openai", "local"])

    def test_select_provider_high_complexity(self):
        provider = self.router.select_provider("high")
        self.assertIn(provider, ["anthropic", "openai"])

    def test_select_provider_default_medium(self):
        provider = self.router.select_provider()
        self.assertIn(provider, ["google", "openai", "local"])

    def test_get_fallback_chain(self):
        chain = self.router.get_fallback_chain("openai")
        self.assertNotIn("openai", chain)
        self.assertIn("local", chain)
        self.assertIn("anthropic", chain)

    def test_get_fallback_chain_excludes_failing(self):
        chain = self.router.get_fallback_chain("unknown")
        self.assertEqual(len(chain), len(self.router.fallback_chain))

    def test_fastest_candidate_selection(self):
        self.router._response_times = {
            "local": 5.0,
            "groq": 0.1,
            "ollama": 0.3,
        }
        fastest = self.router._get_fastest_candidate(["local", "groq", "ollama"])
        self.assertEqual(fastest, "groq")

    def test_fastest_candidate_fallback(self):
        fastest = self.router._get_fastest_candidate(["nonexistent"])
        self.assertEqual(fastest, "local")


class TestAgentLoopFailover(unittest.TestCase):
    def setUp(self):
        self.provider = MagicMock()
        self.provider.name = "local"
        self.provider.model_name = "test-model"
        self.provider.count_message_tokens.return_value = 100
        self.tools = []

    def test_agent_loop_accepts_smart_router(self):
        router = SmartRouter()
        agent = AgentLoop(
            provider=self.provider,
            tools=self.tools,
            config=AgentLoopConfig(max_iterations=1),
            smart_router=router,
        )
        self.assertIsNotNone(agent.smart_router)
        self.assertEqual(agent.smart_router, router)

    def test_agent_loop_default_smart_router(self):
        agent = AgentLoop(
            provider=self.provider,
            tools=self.tools,
            config=AgentLoopConfig(max_iterations=1),
        )
        self.assertIsNotNone(agent.smart_router)
        self.assertIsInstance(agent.smart_router, SmartRouter)

    def test_get_failover_providers_primary_first(self):
        router = SmartRouter()
        agent = AgentLoop(
            provider=self.provider,
            tools=self.tools,
            config=AgentLoopConfig(max_iterations=1),
            smart_router=router,
        )
        providers = agent._get_failover_providers()
        self.assertGreaterEqual(len(providers), 1)
        self.assertEqual(providers[0][0], self.provider)
        self.assertEqual(providers[0][1], "local")

    def test_get_failover_providers_without_router(self):
        agent = AgentLoop(
            provider=self.provider,
            tools=self.tools,
            config=AgentLoopConfig(max_iterations=1),
        )
        agent.smart_router = None
        providers = agent._get_failover_providers()
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0][0], self.provider)


if __name__ == "__main__":
    unittest.main()
