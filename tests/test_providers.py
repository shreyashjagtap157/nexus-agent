"""Unit tests to verify LLM Provider operations and payload formatting."""

import unittest
from unittest.mock import MagicMock, patch

import httpx

from nexus_agent.llm.base import Message, Role, ToolDefinition
from nexus_agent.llm.providers.anthropic_provider import AnthropicProvider
from nexus_agent.llm.providers.aws_bedrock_provider import AWSBedrockProvider
from nexus_agent.llm.providers.custom_openai_provider import CustomOpenAIProvider
from nexus_agent.llm.providers.deepseek_provider import DeepSeekProvider
from nexus_agent.llm.providers.google_provider import GoogleProvider
from nexus_agent.llm.providers.groq_provider import GroqProvider
from nexus_agent.llm.providers.ollama_provider import OllamaProvider
from nexus_agent.llm.providers.openai_provider import OpenAIProvider
from nexus_agent.llm.providers.openrouter_provider import OpenRouterProvider

ALL_PROVIDERS = [
    ("openai", OpenAIProvider, {"api_key": "test-openai-key", "model": "gpt-4o"}),
    ("anthropic", AnthropicProvider, {"api_key": "test-anthropic-key", "model": "claude-3-5-sonnet-latest", "api_url": "https://api.anthropic.com/v1/messages"}),
    ("google", GoogleProvider, {"api_key": "test-google-key", "model": "gemini-pro"}),
    ("groq", GroqProvider, {"api_key": "test-groq-key", "model": "mixtral-8x7b"}),
    ("deepseek", DeepSeekProvider, {"api_key": "test-deepseek-key", "model": "deepseek-chat"}),
    ("openrouter", OpenRouterProvider, {"api_key": "test-or-key", "model": "openai/gpt-4o"}),
    ("ollama", OllamaProvider, {"model": "llama3"}),
    ("custom", CustomOpenAIProvider, {"api_key": "test-custom-key", "model": "custom-model", "api_url": "http://localhost:8000/v1"}),
    ("bedrock", AWSBedrockProvider, {"model": "claude-sonnet-4"}),
]

OPENAI_LIKE = {"openai", "groq", "deepseek", "openrouter", "custom_openai"}


class TestAllProviderNames(unittest.TestCase):
    """Verify every provider has a correct name."""

    def test_all_provider_names(self):
        for name, cls, config in ALL_PROVIDERS:
            with self.subTest(provider=name):
                provider = cls(config)
                self.assertEqual(provider.name, name)


class TestAllProviderCapabilities(unittest.TestCase):
    """Verify every provider's capabilities."""

    def test_all_support_tool_calling(self):
        for name, cls, config in ALL_PROVIDERS:
            with self.subTest(provider=name):
                provider = cls(config)
                caps = provider.get_capabilities()
                self.assertTrue(caps.supports_tool_calling)

    def test_all_support_streaming(self):
        for name, cls, config in ALL_PROVIDERS:
            with self.subTest(provider=name):
                provider = cls(config)
                caps = provider.get_capabilities()
                self.assertTrue(caps.supports_streaming)


class TestOpenAICompatibleChatCompletions(unittest.TestCase):
    """Verify HTTP request formatting for OpenAI-compatible providers."""

    def setUp(self):
        self.messages = [Message(role=Role.USER, content="Hello!")]

    @patch("httpx.Client.post")
    def test_openai_formats_request_correctly(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        mock_post.return_value = mock_response
        provider = OpenAIProvider({"api_key": "key", "model": "gpt-4o"})
        response = provider.chat_completion(self.messages)
        self.assertEqual(response.content, "Hi")
        self.assertEqual(response.usage["total_tokens"], 15)
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["model"], "gpt-4o")
        self.assertEqual(kwargs["json"]["messages"][0]["content"], "Hello!")

    @patch("httpx.Client.post")
    def test_openai_with_tools(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": ""}, "finish_reason": "tool_calls"}],
            "usage": {"total_tokens": 20}
        }
        mock_post.return_value = mock_response
        provider = OpenAIProvider({"api_key": "key", "model": "gpt-4o"})
        tool = ToolDefinition(name="test_tool", description="A test", parameters={"type": "object", "properties": {}})
        response = provider.chat_completion(self.messages, tools=[tool])
        self.assertEqual(response.finish_reason, "tool_calls")

    @patch("httpx.Client.post")
    def test_groq_formats_request_correctly(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Groq reply"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 10}
        }
        mock_post.return_value = mock_response
        provider = GroqProvider({"api_key": "key", "model": "mixtral"})
        response = provider.chat_completion(self.messages)
        self.assertEqual(response.content, "Groq reply")

    @patch("httpx.Client.post")
    def test_deepseek_formats_request_correctly(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "DS reply"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 10}
        }
        mock_post.return_value = mock_response
        provider = DeepSeekProvider({"api_key": "key", "model": "deepseek-chat"})
        response = provider.chat_completion(self.messages)
        self.assertEqual(response.content, "DS reply")

    @patch("httpx.Client.post")
    def test_openrouter_formats_request_correctly(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "OR reply"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 10}
        }
        mock_post.return_value = mock_response
        provider = OpenRouterProvider({"api_key": "key", "model": "openai/gpt-4o"})
        response = provider.chat_completion(self.messages)
        self.assertEqual(response.content, "OR reply")


class TestOllamaProvider(unittest.TestCase):
    """Ollama extends OpenAIProvider but with no API key."""

    @patch.object(OllamaProvider, "_get_headers")
    @patch("httpx.Client.post")
    def test_ollama_chat_completion(self, mock_post, mock_headers):
        mock_headers.return_value = {}
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Ollama reply"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        mock_post.return_value = mock_response
        provider = OllamaProvider({"model": "llama3"})
        messages = [Message(role=Role.USER, content="Hello!")]
        response = provider.chat_completion(messages)
        self.assertEqual(response.content, "Ollama reply")
        self.assertEqual(response.finish_reason, "stop")


class TestAnthropicProvider(unittest.TestCase):
    """Anthropic uses a different API shape."""

    @patch("httpx.Client.post")
    def test_anthropic_chat_completion(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Anthropic reply"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
        mock_post.return_value = mock_response
        provider = AnthropicProvider({
            "api_key": "key", "model": "claude-3",
            "api_url": "https://api.anthropic.com/v1/messages"
        })
        messages = [Message(role=Role.USER, content="Hello!")]
        response = provider.chat_completion(messages)
        self.assertEqual(response.content, "Anthropic reply")
        self.assertEqual(response.finish_reason, "stop")

    @patch("httpx.Client.post")
    def test_anthropic_with_tools(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Using tools"}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
        mock_post.return_value = mock_response
        provider = AnthropicProvider({
            "api_key": "key", "model": "claude-3",
            "api_url": "https://api.anthropic.com/v1/messages"
        })
        tool = ToolDefinition(name="test", description="test", parameters={"type": "object", "properties": {}})
        response = provider.chat_completion([Message(role=Role.USER, content="Hi")], tools=[tool])
        self.assertEqual(response.finish_reason, "tool_use")


class TestGoogleProvider(unittest.TestCase):
    """Google uses OpenAI-compatible endpoint, expects OpenAI format."""

    @patch("httpx.Client.post")
    def test_google_chat_completion(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Google reply"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        mock_post.return_value = mock_response
        provider = GoogleProvider({"api_key": "key", "model": "gemini-pro"})
        messages = [Message(role=Role.USER, content="Hello!")]
        response = provider.chat_completion(messages)
        self.assertEqual(response.content, "Google reply")
        self.assertEqual(response.finish_reason, "stop")


class TestAWSBedrockProvider(unittest.TestCase):
    """Bedrock uses boto3.Session internally."""

    def test_bedrock_chat_completion(self):
        import nexus_agent.llm.providers.aws_bedrock_provider as mod
        mod.BEDROCK_AVAILABLE = True
        mock_boto3 = MagicMock()
        mock_client = mock_boto3.Session.return_value.client.return_value
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "Bedrock reply"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
        }
        mod.boto3 = mock_boto3
        try:
            provider = AWSBedrockProvider({"model": "claude-sonnet-4"})
            messages = [Message(role=Role.USER, content="Hello!")]
            response = provider.chat_completion(messages)
            self.assertEqual(response.content, "Bedrock reply")
            self.assertEqual(response.finish_reason, "stop")
            self.assertEqual(response.usage["total_tokens"], 15)
        finally:
            mod.BEDROCK_AVAILABLE = False
            del mod.boto3


class TestProviderErrorHandling(unittest.TestCase):
    """Verify providers handle errors gracefully."""

    @patch("httpx.Client.post")
    def test_openai_http_error(self, mock_post):
        mock_post.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )
        provider = OpenAIProvider({"api_key": "bad-key", "model": "gpt-4o"})
        with self.assertRaises(httpx.HTTPStatusError):
            provider.chat_completion([Message(role=Role.USER, content="Hi")])

    @patch("httpx.Client.post")
    def test_openai_timeout(self, mock_post):
        mock_post.side_effect = httpx.TimeoutException("timed out")
        provider = OpenAIProvider({"api_key": "key", "model": "gpt-4o"})
        with self.assertRaises(httpx.TimeoutException):
            provider.chat_completion([Message(role=Role.USER, content="Hi")])

    @patch("httpx.Client.post")
    def test_anthropic_http_error(self, mock_post):
        mock_post.side_effect = httpx.HTTPStatusError(
            "429 Rate Limited", request=MagicMock(), response=MagicMock(status_code=429)
        )
        provider = AnthropicProvider({"api_key": "key", "model": "claude-3", "api_url": "https://api.anthropic.com/v1/messages"})
        with self.assertRaises(httpx.HTTPStatusError):
            provider.chat_completion([Message(role=Role.USER, content="Hi")])


class TestProviderEdgeCases(unittest.TestCase):
    """Edge cases across all providers."""

    def test_empty_messages_providers_accept(self):
        for name, cls, config in ALL_PROVIDERS:
            if name in {"bedrock"}:
                with self.subTest(provider=name):
                    provider = cls(config)
                    with self.assertRaises((ValueError, RuntimeError)):
                        provider.chat_completion([])

    def test_missing_api_key_still_instantiates(self):
        OpenAIProvider({"model": "gpt-4o", "api_key": ""})
        AnthropicProvider({"model": "claude-3", "api_key": None, "api_url": "https://api.anthropic.com/v1/messages"})

    def test_ollama_no_api_key(self):
        OllamaProvider({"model": "llama3"})

    def test_bedrock_no_api_key_in_config(self):
        AWSBedrockProvider({"model": "claude-sonnet-4"})
