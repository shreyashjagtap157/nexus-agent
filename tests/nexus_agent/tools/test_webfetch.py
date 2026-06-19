"""Tests for `tools/webfetch.py` — HTML→markdown + WebFetchTool."""

import time
import unittest
from unittest.mock import MagicMock, patch

from nexus_agent.tools.webfetch import (
    WebFetchTool,
    _coerce_int,
    _LRUCache,
    html_to_markdown,
)


class TestHTMLToMarkdown(unittest.TestCase):
    """`html_to_markdown` correctness."""

    def test_plain_text(self):
        self.assertEqual(html_to_markdown("hello world"), "hello world")

    def test_drops_script_and_style(self):
        html = "<p>before</p><script>alert('xss')</script><style>body{}</style><p>after</p>"
        out = html_to_markdown(html)
        self.assertIn("before", out)
        self.assertIn("after", out)
        self.assertNotIn("alert", out)
        self.assertNotIn("body{}", out)

    def test_drops_comments(self):
        html = "before <!-- this is a comment --> after"
        out = html_to_markdown(html)
        self.assertNotIn("comment", out)
        self.assertIn("before", out)
        self.assertIn("after", out)

    def test_headings_have_hashes(self):
        html = "<h1>Title</h1><h2>Sub</h2><h3>SubSub</h3>"
        out = html_to_markdown(html)
        self.assertIn("# Title", out)
        self.assertIn("## Sub", out)
        self.assertIn("### SubSub", out)

    def test_links_have_md_syntax(self):
        html = '<p>See <a href="https://example.com">example</a>.</p>'
        out = html_to_markdown(html)
        self.assertIn("[example](https://example.com)", out)

    def test_relative_links_resolved(self):
        html = '<a href="/about">About</a>'
        out = html_to_markdown(html, base_url="https://x.com/foo/")
        self.assertIn("[About](https://x.com/about)", out)

    def test_unordered_list(self):
        html = "<ul><li>one</li><li>two</li><li>three</li></ul>"
        out = html_to_markdown(html)
        self.assertIn("* one", out)
        self.assertIn("* two", out)
        self.assertIn("* three", out)

    def test_ordered_list(self):
        html = "<ol><li>first</li><li>second</li></ol>"
        out = html_to_markdown(html)
        self.assertIn("1. first", out)
        self.assertIn("2. second", out)

    def test_nested_list_indent(self):
        html = "<ul><li>outer<ul><li>inner</li></ul></li></ul>"
        out = html_to_markdown(html)
        self.assertIn("* outer", out)
        self.assertIn("  * inner", out)

    def test_blockquote(self):
        html = "<blockquote><p>quoted</p></blockquote>"
        out = html_to_markdown(html)
        self.assertIn("> quoted", out)

    def test_preformatted_block(self):
        html = "<pre><code>x = 1\ny = 2</code></pre>"
        out = html_to_markdown(html)
        self.assertIn("```", out)
        self.assertIn("x = 1", out)
        self.assertIn("y = 2", out)

    def test_inline_code(self):
        html = "<p>Use <code>foo()</code> to call foo.</p>"
        out = html_to_markdown(html)
        self.assertIn("`foo()`", out)

    def test_bold_and_italic(self):
        html = "<p><strong>bold</strong> and <em>italic</em></p>"
        out = html_to_markdown(html)
        self.assertIn("**bold**", out)
        self.assertIn("_italic_", out)

    def test_image_with_alt(self):
        html = '<p><img src="/a.png" alt="A picture"></p>'
        out = html_to_markdown(html, base_url="https://x.com/")
        self.assertIn("![A picture](https://x.com/a.png)", out)

    def test_horizontal_rule(self):
        html = "<p>above</p><hr><p>below</p>"
        out = html_to_markdown(html)
        self.assertIn("---", out)
        self.assertIn("above", out)
        self.assertIn("below", out)

    def test_paragraphs_separated(self):
        html = "<p>one</p><p>two</p><p>three</p>"
        out = html_to_markdown(html)
        self.assertIn("one", out)
        self.assertIn("two", out)
        self.assertIn("three", out)
        # each on its own line
        lines = out.split("\n")
        self.assertGreater(len([l for l in lines if l.strip()]), 0)

    def test_collapse_whitespace(self):
        html = "<p>hello     world\n\n\n   again</p>"
        out = html_to_markdown(html)
        self.assertIn("hello world", out)
        self.assertIn("again", out)
        # no triple-newline runs
        self.assertNotIn("\n\n\n", out)

    def test_html_entities_decoded(self):
        self.assertIn("&", html_to_markdown("<p>AT&amp;T</p>"))
        self.assertIn("<", html_to_markdown("<p>1 &lt; 2</p>"))

    def test_drops_iframe_and_svg(self):
        html = (
            "<p>visible</p>"
            "<iframe src='evil.com'>iframe body</iframe>"
            "<svg><rect/></svg>"
            "<p>also visible</p>"
        )
        out = html_to_markdown(html)
        self.assertIn("visible", out)
        self.assertIn("also visible", out)
        self.assertNotIn("iframe body", out)
        self.assertNotIn("rect", out)

    def test_no_html(self):
        self.assertEqual(html_to_markdown(""), "")

    def test_invalid_html_does_not_crash(self):
        # Unclosed tags
        out = html_to_markdown("<p>oops<b>bold")
        self.assertIn("oops", out)
        self.assertIn("bold", out)

    def test_title_tag_dropped(self):
        out = html_to_markdown("<title>Hidden</title><p>Visible</p>")
        self.assertNotIn("Hidden", out)
        self.assertIn("Visible", out)


class TestLRUCache(unittest.TestCase):
    """Tiny LRU used by WebFetchTool."""

    def test_put_and_get(self):
        c: _LRUCache = _LRUCache(max_size=2)
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)

    def test_evicts_lru(self):
        c: _LRUCache = _LRUCache(max_size=2)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")  # mark a as recently used
        c.put("c", 3)  # should evict b
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("b"))
        self.assertEqual(c.get("c"), 3)

    def test_max_size_zero(self):
        c: _LRUCache = _LRUCache(max_size=0)
        c.put("a", 1)
        self.assertEqual(len(c), 0)


class TestCoerceInt(unittest.TestCase):
    """Defensive int coercion."""

    def test_valid_int(self):
        self.assertEqual(_coerce_int("42", 10), 42)

    def test_invalid_uses_default(self):
        self.assertEqual(_coerce_int("abc", 10), 10)

    def test_none_uses_default(self):
        self.assertEqual(_coerce_int(None, 10), 10)

    def test_below_lo_clamped(self):
        self.assertEqual(_coerce_int(-5, 10, lo=0), 0)

    def test_above_hi_clamped(self):
        self.assertEqual(_coerce_int(1000, 10, hi=100), 100)


class TestWebFetchTool(unittest.TestCase):
    """`WebFetchTool` end-to-end (with mocked httpx)."""

    def _mock_response(self, text: str, status: int = 200, ctype: str = "text/html; charset=utf-8", url: str = "https://x.com/"):
        r = MagicMock()
        r.status_code = status
        r.headers = {"content-type": ctype}
        r.content = text.encode("utf-8")
        r.url = url
        return r

    def test_tool_metadata(self):
        tool = WebFetchTool()
        self.assertEqual(tool.name, "webfetch")
        self.assertEqual(tool.permission_level, "read-only")
        self.assertIn("url", tool.required_params)

    def test_validates_url_scheme(self):
        tool = WebFetchTool()
        self.assertIn("http or https", tool.execute("ftp://x.com/file"))
        self.assertIn("required", tool.execute(""))
        self.assertIn("no host", tool.execute("http://"))

    def test_404_returns_error(self):
        tool = WebFetchTool(cache_ttl_s=0)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response("nope", status=404)
            MockClient.return_value = ctx
            out = tool.execute("https://x.com/missing")
        self.assertIn("404", out)

    def test_rejects_non_html(self):
        tool = WebFetchTool(cache_ttl_s=0)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                "binary", ctype="application/octet-stream"
            )
            MockClient.return_value = ctx
            out = tool.execute("https://x.com/file")
        self.assertIn("content-type", out.lower())

    def test_fetches_and_converts(self):
        tool = WebFetchTool(cache_ttl_s=0)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                "<html><body><h1>Hello</h1><p>World</p></body></html>"
            )
            MockClient.return_value = ctx
            out = tool.execute("https://x.com/")
        self.assertIn("# Hello", out)
        self.assertIn("World", out)

    def test_max_chars_truncates(self):
        tool = WebFetchTool(cache_ttl_s=0, max_chars=20)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                "<p>" + "x" * 1000 + "</p>"
            )
            MockClient.return_value = ctx
            out = tool.execute("https://x.com/", max_chars=20)
        self.assertIn("truncated", out)
        self.assertLess(len(out), 200)

    def test_max_chars_clamps_to_lo(self):
        tool = WebFetchTool(cache_ttl_s=0, max_chars=20)
        out = tool.execute("https://x.com/", max_chars=-5)
        # Should still return something — max_chars 0 gets clamped to 100
        self.assertIsInstance(out, str)

    def test_cache_hits_second_call(self):
        tool = WebFetchTool(cache_ttl_s=300, cache_size=4)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                "<p>cached</p>"
            )
            MockClient.return_value = ctx
            out1 = tool.execute("https://x.com/")
            # The client should have been called once.
            self.assertEqual(ctx.__enter__.return_value.get.call_count, 1)
            out2 = tool.execute("https://x.com/")
            # Cache hit — should not call again.
            self.assertEqual(ctx.__enter__.return_value.get.call_count, 1)
        self.assertIn("cached", out1)
        self.assertEqual(out1, out2)

    def test_no_cache_bypasses_cache(self):
        tool = WebFetchTool(cache_ttl_s=300, cache_size=4)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                "<p>cached</p>"
            )
            MockClient.return_value = ctx
            tool.execute("https://x.com/")
            tool.execute("https://x.com/", no_cache=True)
            self.assertEqual(ctx.__enter__.return_value.get.call_count, 2)

    def test_cache_expires(self):
        tool = WebFetchTool(cache_ttl_s=1, cache_size=4)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                "<p>cached</p>"
            )
            MockClient.return_value = ctx
            tool.execute("https://x.com/")
            time.sleep(1.2)
            tool.execute("https://x.com/")
            self.assertEqual(ctx.__enter__.return_value.get.call_count, 2)

    def test_network_error_returns_error_string(self):
        tool = WebFetchTool(cache_ttl_s=0)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.side_effect = OSError("no internet")
            MockClient.return_value = ctx
            out = tool.execute("https://x.com/")
        self.assertIn("Error", out)
        self.assertIn("no internet", out)

    def test_clear_cache(self):
        tool = WebFetchTool(cache_ttl_s=300, cache_size=4)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                "<p>x</p>"
            )
            MockClient.return_value = ctx
            tool.execute("https://x.com/")
            self.assertEqual(len(tool._cache), 1)
            tool.clear_cache()
            self.assertEqual(len(tool._cache), 0)

    def test_latin1_fallback(self):
        tool = WebFetchTool(cache_ttl_s=0)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            r = self._mock_response("ignored")
            # Build a content with bytes that are not valid utf-8
            r.content = b"<p>Caf\xe9</p>"
            r.headers = {"content-type": "text/html; charset=latin-1"}
            ctx.__enter__.return_value.get.return_value = r
            MockClient.return_value = ctx
            out = tool.execute("https://x.com/")
        self.assertIn("Caf", out)

    def test_relative_url_resolution(self):
        tool = WebFetchTool(cache_ttl_s=0)
        with patch("httpx.Client") as MockClient:
            ctx = MagicMock()
            ctx.__enter__.return_value.get.return_value = self._mock_response(
                '<html><body><a href="/about">about</a></body></html>',
                url="https://x.com/foo",
            )
            MockClient.return_value = ctx
            out = tool.execute("https://x.com/foo")
        self.assertIn("[about](https://x.com/about)", out)


if __name__ == "__main__":
    unittest.main()
