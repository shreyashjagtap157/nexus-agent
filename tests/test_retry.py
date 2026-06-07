"""Tests for the retry/backoff/rate-limit module in `llm/retry.py`."""

import time
import unittest
from unittest.mock import MagicMock, patch

import httpx

from nexus_agent.llm.retry import (
    RETRYABLE_STATUS_CODES,
    RetryPolicy,
    RetryStats,
    _is_retryable,
    _retry_after_seconds,
    chat_with_retry,
    with_retry,
)


class TestRetryPolicy(unittest.TestCase):
    """`RetryPolicy` dataclass behavior."""

    def test_defaults(self):
        p = RetryPolicy()
        self.assertEqual(p.max_attempts, 3)
        self.assertEqual(p.initial_backoff_s, 1.0)
        self.assertEqual(p.max_backoff_s, 30.0)
        self.assertEqual(p.backoff_multiplier, 2.0)
        self.assertTrue(p.jitter)
        self.assertEqual(p.retry_on_status, RETRYABLE_STATUS_CODES)
        self.assertIn(429, p.retry_on_status)
        self.assertIn(500, p.retry_on_status)
        self.assertIn(503, p.retry_on_status)

    def test_backoff_grows(self):
        p = RetryPolicy(
            max_attempts=5,
            initial_backoff_s=1.0,
            max_backoff_s=100.0,
            backoff_multiplier=2.0,
            jitter=False,
        )
        d0 = p.backoff_for(0)
        d1 = p.backoff_for(1)
        d2 = p.backoff_for(2)
        d3 = p.backoff_for(3)
        self.assertEqual(d0, 1.0)
        self.assertEqual(d1, 2.0)
        self.assertEqual(d2, 4.0)
        self.assertEqual(d3, 8.0)

    def test_backoff_caps_at_max(self):
        p = RetryPolicy(
            max_attempts=10,
            initial_backoff_s=10.0,
            max_backoff_s=15.0,
            backoff_multiplier=2.0,
            jitter=False,
        )
        d0 = p.backoff_for(0)
        d4 = p.backoff_for(4)
        self.assertEqual(d0, 10.0)
        self.assertEqual(d4, 15.0)  # 10*16=160 capped at 15

    def test_jitter_keeps_in_range(self):
        p = RetryPolicy(
            max_attempts=5,
            initial_backoff_s=1.0,
            max_backoff_s=30.0,
            backoff_multiplier=2.0,
            jitter=True,
        )
        for _ in range(50):
            d = p.backoff_for(2)  # base 4.0
            self.assertGreaterEqual(d, 4.0 * 0.75)
            self.assertLessEqual(d, 4.0 * 1.25)

    def test_retryable_codes_cover_required(self):
        self.assertIn(429, RetryPolicy().retry_on_status)
        self.assertIn(500, RetryPolicy().retry_on_status)
        self.assertIn(502, RetryPolicy().retry_on_status)
        self.assertIn(503, RetryPolicy().retry_on_status)
        self.assertIn(504, RetryPolicy().retry_on_status)
        self.assertNotIn(400, RetryPolicy().retry_on_status)
        self.assertNotIn(401, RetryPolicy().retry_on_status)
        self.assertNotIn(403, RetryPolicy().retry_on_status)
        self.assertNotIn(404, RetryPolicy().retry_on_status)


class TestIsRetryable(unittest.TestCase):
    """Classification of which exceptions trigger retry."""

    def test_timeout_is_retryable(self):
        policy = RetryPolicy()
        self.assertTrue(_is_retryable(httpx.ConnectTimeout("x"), policy))
        self.assertTrue(_is_retryable(httpx.ReadTimeout("x"), policy))
        self.assertTrue(_is_retryable(httpx.WriteTimeout("x"), policy))
        self.assertTrue(_is_retryable(httpx.PoolTimeout("x"), policy))

    def test_network_error_is_retryable(self):
        policy = RetryPolicy()
        self.assertTrue(_is_retryable(httpx.ConnectError("x"), policy))
        self.assertTrue(_is_retryable(httpx.NetworkError("x"), policy))

    def test_connection_timeout_error_is_retryable(self):
        policy = RetryPolicy()
        self.assertTrue(_is_retryable(ConnectionError("x"), policy))
        self.assertTrue(_is_retryable(TimeoutError("x"), policy))

    def test_http_status_codes(self):
        policy = RetryPolicy()
        for code in (408, 425, 429, 500, 502, 503, 504):
            req = httpx.Request("GET", "https://x")
            resp = httpx.Response(code, request=req)
            err = httpx.HTTPStatusError("x", request=req, response=resp)
            self.assertTrue(_is_retryable(err, policy), f"expected retry for {code}")

    def test_non_retryable_status_codes(self):
        policy = RetryPolicy()
        for code in (400, 401, 403, 404, 422):
            req = httpx.Request("GET", "https://x")
            resp = httpx.Response(code, request=req)
            err = httpx.HTTPStatusError("x", request=req, response=resp)
            self.assertFalse(_is_retryable(err, policy), f"expected no retry for {code}")

    def test_value_error_not_retryable(self):
        self.assertFalse(_is_retryable(ValueError("x"), RetryPolicy()))

    def test_runtime_error_not_retryable(self):
        self.assertFalse(_is_retryable(RuntimeError("x"), RetryPolicy()))


class TestRetryAfterSeconds(unittest.TestCase):
    """Parse server-suggested `Retry-After` header."""

    def test_returns_none_when_no_header(self):
        req = httpx.Request("GET", "https://x")
        resp = httpx.Response(429, request=req)
        err = httpx.HTTPStatusError("x", request=req, response=resp)
        self.assertIsNone(_retry_after_seconds(err))

    def test_parses_seconds(self):
        req = httpx.Request("GET", "https://x")
        resp = httpx.Response(429, request=req, headers={"Retry-After": "12"})
        err = httpx.HTTPStatusError("x", request=req, response=resp)
        self.assertEqual(_retry_after_seconds(err), 12.0)

    def test_parses_zero_seconds(self):
        req = httpx.Request("GET", "https://x")
        resp = httpx.Response(429, request=req, headers={"Retry-After": "0"})
        err = httpx.HTTPStatusError("x", request=req, response=resp)
        self.assertEqual(_retry_after_seconds(err), 0.0)

    def test_ignores_http_date(self):
        req = httpx.Request("GET", "https://x")
        resp = httpx.Response(429, request=req, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
        err = httpx.HTTPStatusError("x", request=req, response=resp)
        self.assertIsNone(_retry_after_seconds(err))

    def test_non_http_error_returns_none(self):
        self.assertIsNone(_retry_after_seconds(ValueError("x")))


class TestWithRetry(unittest.TestCase):
    """End-to-end `with_retry` behavior."""

    def test_success_on_first_attempt(self):
        result, stats = with_retry(lambda: "ok")
        self.assertEqual(result, "ok")
        self.assertEqual(stats.attempts, 1)
        self.assertEqual(stats.total_sleep_s, 0.0)
        self.assertIsNone(stats.last_error)

    def test_success_after_retry(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.ReadTimeout("nope")
            return "ok"

        p = RetryPolicy(max_attempts=5, initial_backoff_s=0.001, jitter=False)
        result, stats = with_retry(flaky, policy=p)
        self.assertEqual(result, "ok")
        self.assertEqual(stats.attempts, 3)
        self.assertGreater(stats.total_sleep_s, 0.0)

    def test_gives_up_after_max_attempts(self):
        def always_fail():
            raise httpx.ReadTimeout("nope")

        p = RetryPolicy(max_attempts=3, initial_backoff_s=0.001, jitter=False)
        with self.assertRaises(httpx.ReadTimeout):
            with_retry(always_fail, policy=p)

    def test_does_not_retry_non_retryable(self):
        calls = {"n": 0}

        def fail():
            calls["n"] += 1
            raise ValueError("nope")

        p = RetryPolicy(max_attempts=5, initial_backoff_s=0.001)
        with self.assertRaises(ValueError):
            with_retry(fail, policy=p)
        self.assertEqual(calls["n"], 1)

    def test_does_not_retry_400(self):
        calls = {"n": 0}

        def fail():
            calls["n"] += 1
            req = httpx.Request("GET", "https://x")
            resp = httpx.Response(400, request=req)
            raise httpx.HTTPStatusError("nope", request=req, response=resp)

        p = RetryPolicy(max_attempts=5, initial_backoff_s=0.001)
        with self.assertRaises(httpx.HTTPStatusError):
            with_retry(fail, policy=p)
        self.assertEqual(calls["n"], 1)

    def test_records_last_status(self):
        def fail():
            req = httpx.Request("GET", "https://x")
            resp = httpx.Response(429, request=req, headers={"Retry-After": "1"})
            raise httpx.HTTPStatusError("nope", request=req, response=resp)

        p = RetryPolicy(max_attempts=2, initial_backoff_s=0.001, jitter=False)
        with self.assertRaises(httpx.HTTPStatusError):
            result, stats = with_retry(fail, policy=p)

    def test_uses_retry_after_header(self):
        """When server sends Retry-After, we use that instead of backoff."""
        sleeps: list[float] = []

        def fake_sleep(s):
            sleeps.append(s)

        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                req = httpx.Request("GET", "https://x")
                resp = httpx.Response(429, request=req, headers={"Retry-After": "5"})
                raise httpx.HTTPStatusError("rate limited", request=req, response=resp)
            return "ok"

        p = RetryPolicy(max_attempts=3, initial_backoff_s=1.0, jitter=False)
        with patch("nexus_agent.llm.retry.time.sleep", side_effect=fake_sleep):
            result, stats = with_retry(flaky, policy=p)
        self.assertEqual(result, "ok")
        self.assertEqual(len(sleeps), 1)
        self.assertEqual(sleeps[0], 5.0)  # used Retry-After, not 1.0 backoff
        self.assertEqual(stats.total_sleep_s, 5.0)

    def test_on_retry_callback_fires(self):
        sleeps: list[float] = []
        cb_calls: list[tuple[int, float, BaseException]] = []

        def fake_sleep(s):
            sleeps.append(s)

        def cb(attempt, delay, exc):
            cb_calls.append((attempt, delay, exc))

        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise httpx.ReadTimeout("x")
            return "ok"

        p = RetryPolicy(max_attempts=3, initial_backoff_s=0.001, jitter=False)
        with patch("nexus_agent.llm.retry.time.sleep", side_effect=fake_sleep):
            with_retry(flaky, policy=p, on_retry=cb)
        self.assertEqual(len(cb_calls), 1)
        self.assertEqual(cb_calls[0][0], 1)  # first retry
        self.assertGreater(cb_calls[0][1], 0.0)
        self.assertIsInstance(cb_calls[0][2], httpx.ReadTimeout)

    def test_on_retry_callback_swallows_exceptions(self):
        """A buggy on_retry callback must not crash the retry loop."""
        sleeps: list[float] = []

        def fake_sleep(s):
            sleeps.append(s)

        def bad_cb(attempt, delay, exc):
            raise RuntimeError("buggy callback")

        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise httpx.ReadTimeout("x")
            return "ok"

        p = RetryPolicy(max_attempts=3, initial_backoff_s=0.001, jitter=False)
        with patch("nexus_agent.llm.retry.time.sleep", side_effect=fake_sleep):
            result, stats = with_retry(flaky, policy=p, on_retry=bad_cb)
        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 2)

    def test_max_attempts_one_means_no_retry(self):
        calls = {"n": 0}

        def fail():
            calls["n"] += 1
            raise httpx.ReadTimeout("x")

        p = RetryPolicy(max_attempts=1)
        with self.assertRaises(httpx.ReadTimeout):
            with_retry(fail, policy=p)
        self.assertEqual(calls["n"], 1)


class TestChatWithRetry(unittest.TestCase):
    """`chat_with_retry` wraps a `LLMProvider` correctly."""

    def _make_response(self, content="hello"):
        from nexus_agent.llm.base import LLMResponse
        return LLMResponse(
            content=content,
            tool_calls=[],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            model="m",
            finish_reason="stop",
        )

    def test_chat_completion_retries_then_succeeds(self):
        from nexus_agent.llm.base import Message, Role
        provider = MagicMock()
        provider.chat_completion.side_effect = [
            httpx.ReadTimeout("x"),
            httpx.ReadTimeout("x"),
            self._make_response("finally"),
        ]
        p = RetryPolicy(max_attempts=3, initial_backoff_s=0.001, jitter=False)
        result, stats = chat_with_retry(
            provider,
            [Message(role=Role.USER, content="hi")],
            policy=p,
        )
        self.assertEqual(result.content, "finally")
        self.assertEqual(stats.attempts, 3)
        self.assertEqual(provider.chat_completion.call_count, 3)

    def test_chat_completion_propagates_non_retryable(self):
        from nexus_agent.llm.base import Message, Role
        provider = MagicMock()
        provider.chat_completion.side_effect = ValueError("nope")
        p = RetryPolicy(max_attempts=5, initial_backoff_s=0.001)
        with self.assertRaises(ValueError):
            chat_with_retry(
                provider,
                [Message(role=Role.USER, content="hi")],
                policy=p,
            )
        self.assertEqual(provider.chat_completion.call_count, 1)

    def test_streaming_returns_iter(self):
        from nexus_agent.llm.base import StreamChunk
        provider = MagicMock()
        chunks = [StreamChunk(content="a", finish_reason=None)]
        provider.chat_completion_stream.return_value = iter(chunks)
        result, stats = chat_with_retry(
            provider,
            [],
            stream=True,
        )
        out = list(result)
        self.assertEqual(out, chunks)
        self.assertEqual(stats.attempts, 1)
        self.assertEqual(provider.chat_completion.call_count, 0)
        self.assertEqual(provider.chat_completion_stream.call_count, 1)

    def test_pass_through_kwargs(self):
        from nexus_agent.llm.base import Message, Role
        provider = MagicMock()
        provider.chat_completion.return_value = self._make_response()
        chat_with_retry(
            provider,
            [Message(role=Role.USER, content="hi")],
            temperature=0.7,
            max_tokens=1234,
            stop=["END"],
        )
        # chat_completion(messages, tools, temperature, max_tokens, **kwargs)
        # so temperature & max_tokens go positionally, extra kwargs (stop) go to **kwargs
        call_args = provider.chat_completion.call_args
        self.assertEqual(call_args.args[0], [Message(role=Role.USER, content="hi")])
        self.assertEqual(call_args.args[2], 0.7)  # temperature
        self.assertEqual(call_args.args[3], 1234)  # max_tokens
        self.assertEqual(call_args.kwargs.get("stop"), ["END"])


if __name__ == "__main__":
    unittest.main()
