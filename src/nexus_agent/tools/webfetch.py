"""
Web Fetch Tool — Fetch a URL and convert its HTML to clean text/markdown.

The conversion uses only the Python standard library (`html.parser`) so
the tool works in offline-restricted environments without requiring
`beautifulsoup4` / `markdownify` / `html2text`.

Features:
- GET a URL with httpx, follow redirects, configurable timeout.
- Strip <script>, <style>, <noscript>, <iframe>, <svg>, comments.
- Convert common block tags (h1-h6, p, br, li, blockquote, pre) into
  markdown-ish newlines and `*`/`#` decorations.
- Preserve inline links `[text](url)`.
- Cap output length so a giant page doesn't blow the LLM's context.
- Caches by (url, mtime-of-cache) in a per-instance dict; `no_cache=True`
  bypasses. TTL configurable.

The tool is read-only — it never writes anywhere on disk.
"""

from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)


# Tags that should be removed entirely (their text content is dropped).
_DROP_TAGS: frozenset[str] = frozenset({
    "script", "style", "noscript", "iframe", "svg", "canvas",
    "template", "form", "input", "button", "select", "option",
    "object", "embed", "applet", "base", "link", "meta", "title", "head",
})

# Block-level tags that should produce a newline boundary.
_BLOCK_TAGS: frozenset[str] = frozenset({
    "p", "div", "section", "article", "header", "footer", "main",
    "aside", "nav", "ul", "ol", "table", "thead", "tbody", "tfoot",
    "tr", "figure", "figcaption", "hr", "address",
})

# Headings produce `#` decorations.
_HEADING_TAGS: frozenset[str] = frozenset({f"h{i}" for i in range(1, 7)})


def _coerce_int(value: Any, default: int, *, lo: int = 0, hi: int | None = None) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if n < lo:
        return lo
    if hi is not None and n > hi:
        return hi
    return n


class _HTMLToMarkdown(HTMLParser):
    """Streaming HTML→text/markdown converter.

    Walks the document, building an output string with sensible
    whitespace and structural decorations. Not a full CommonMark
    converter — just enough for an LLM to read a web page.
    """

    def __init__(self, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        # A list of "lines". Each entry is one of:
        #   - a non-empty string (a real line, e.g. "Hello world")
        #   - "" (one blank line)
        # The final result is "\n".join(buf), so an empty list element
        # becomes a single newline in the output.
        self._buf: list[str] = []
        self._link_stack: list[str] = []  # currently open href
        self._tag_stack: list[str] = []
        # Stack of (tag, buf_length_at_open) so we can rewind line ranges
        # at close time (used by blockquote to prefix all its lines).
        self._open_marks: list[tuple[str, int]] = []
        self._list_stack: list[int] = []  # depth at each <ol>/<ul>
        self._list_counter: list[int] = []  # running count for <ol>
        self._in_pre = False
        self._suppressed_depth = 0
        self._base_url = base_url
        self._pending_text: str = ""  # current in-progress text run

    # --- helpers ---

    def _flush_text(self) -> None:
        """Move any pending text into the buffer as a new line."""
        if not self._pending_text:
            return
        if self._suppressed_depth:
            self._pending_text = ""
            return
        if self._in_pre:
            # In pre mode, text is appended as-is to the current line
            if self._buf and self._buf[-1] != "":
                self._buf[-1] = self._buf[-1] + self._pending_text
            else:
                self._buf.append(self._pending_text)
        else:
            self._buf.append(self._pending_text)
        self._pending_text = ""

    def _text(self, s: str) -> None:
        if self._suppressed_depth:
            return
        if self._in_pre:
            self._pending_text += s
            return
        # Collapse runs of whitespace to a single space
        s = re.sub(r"\s+", " ", s)
        # If pending is empty and s starts with whitespace, skip leading ws
        s = s.lstrip() if not self._pending_text else s
        if s:
            self._pending_text += s

    def _hard_break(self, n: int = 1) -> None:
        if self._suppressed_depth:
            self._pending_text = ""
            return
        self._flush_text()
        # Pop trailing empty lines, then add `n` blank lines (so n=2
        # creates a paragraph break: one blank line between paragraphs).
        while self._buf and self._buf[-1] == "":
            self._buf.pop()
        for _ in range(n):
            self._buf.append("")

    def _ensure_blank_line(self) -> None:
        if self._suppressed_depth:
            self._pending_text = ""
            return
        self._flush_text()
        if not self._buf:
            return
        if self._buf[-1] != "":
            self._buf.append("")

    # --- tag handlers ---

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _DROP_TAGS:
            self._suppressed_depth += 1
            self._tag_stack.append(tag)
            return
        if tag == "br":
            self._hard_break(1)
            self._tag_stack.append(tag)
            return
        if tag == "hr":
            self._ensure_blank_line()
            self._pending_text = "---"
            self._hard_break(2)
            self._tag_stack.append(tag)
            return
        if tag in _HEADING_TAGS:
            level = int(tag[1])
            self._ensure_blank_line()
            self._pending_text = "#" * level + " "
            self._tag_stack.append(tag)
            self._open_marks.append((tag, len(self._buf)))
            return
        if tag == "p":
            self._ensure_blank_line()
            self._tag_stack.append(tag)
            self._open_marks.append((tag, len(self._buf)))
            return
        if tag == "blockquote":
            self._ensure_blank_line()
            self._tag_stack.append(tag)
            self._open_marks.append((tag, len(self._buf)))
            return
        if tag in ("ul", "ol"):
            self._ensure_blank_line()
            self._list_stack.append(len(self._list_stack))
            self._list_counter.append(0 if tag == "ol" else -1)
            self._tag_stack.append(tag)
            return
        if tag == "li":
            self._ensure_blank_line()
            depth = len(self._list_stack) - 1
            if depth < 0:
                depth = 0
            indent = "  " * depth
            counter = self._list_counter[-1] if self._list_counter else -1
            if counter >= 0:
                self._list_counter[-1] = counter + 1
                self._pending_text = f"{indent}{counter + 1}. "
            else:
                self._pending_text = f"{indent}* "
            self._tag_stack.append(tag)
            return
        if tag == "pre":
            self._ensure_blank_line()
            self._buf.append("```")
            self._in_pre = True
            self._tag_stack.append(tag)
            return
        if tag == "code" and not self._in_pre:
            self._pending_text += "`"
            self._tag_stack.append(tag)
            return
        if tag == "a":
            href = None
            for k, v in attrs:
                if k.lower() == "href" and v:
                    href = v
                    break
            if href:
                full = urljoin(self._base_url, href)
                self._link_stack.append(full)
                self._pending_text += "["
            else:
                self._link_stack.append("")
            self._tag_stack.append(tag)
            return
        if tag in ("strong", "b"):
            self._pending_text += "**"
            self._tag_stack.append(tag)
            return
        if tag in ("em", "i"):
            self._pending_text += "_"
            self._tag_stack.append(tag)
            return
        if tag == "img":
            alt = None
            src = None
            for k, v in attrs:
                kl = k.lower()
                if kl == "alt":
                    alt = v or ""
                elif kl == "src":
                    src = v
            if alt or src:
                self._pending_text += f"![{alt or ''}]"
                if src:
                    full = urljoin(self._base_url, src)
                    self._pending_text += f"({full})"
            self._tag_stack.append(tag)
            return
        if tag in _BLOCK_TAGS:
            self._ensure_blank_line()
            self._tag_stack.append(tag)
            return
        self._tag_stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._tag_stack:
            return
        if tag in self._tag_stack:
            idx = len(self._tag_stack) - 1 - self._tag_stack[::-1].index(tag)
            closing = self._tag_stack[idx:]
            self._tag_stack = self._tag_stack[:idx]
        else:
            closing = (tag,)

        for closed in closing:
            self._close_one(closed)

    def _close_one(self, tag: str) -> None:
        # Look up the buffer length at the moment this tag was opened.
        # We pop from the end to handle nested cases correctly.
        mark_idx = -1
        for i in range(len(self._open_marks) - 1, -1, -1):
            if self._open_marks[i][0] == tag:
                mark_idx = i
                break
        open_buf_len = self._open_marks[mark_idx][1] if mark_idx >= 0 else -1
        if mark_idx >= 0:
            self._open_marks.pop(mark_idx)

        if tag in _DROP_TAGS:
            if self._suppressed_depth > 0:
                self._suppressed_depth -= 1
            return
        if tag in _HEADING_TAGS:
            self._hard_break(2)
            return
        if tag == "p":
            self._hard_break(2)
            return
        if tag == "blockquote":
            # Prefix every line added since the open mark with "> ".
            if open_buf_len >= 0:
                for k in range(open_buf_len, len(self._buf)):
                    line = self._buf[k]
                    if line and not line.startswith("> "):
                        self._buf[k] = "> " + line
            self._hard_break(2)
            return
        if tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            if self._list_counter:
                self._list_counter.pop()
            self._hard_break(1)
            return
        if tag == "pre":
            self._hard_break(1)
            self._buf.append("```")
            self._in_pre = False
            self._hard_break(1)
            return
        if tag == "code" and not self._in_pre:
            self._pending_text += "`"
            return
        if tag == "a":
            if self._link_stack:
                href = self._link_stack.pop()
            else:
                href = ""
            if href:
                self._pending_text += f"]({href})"
            return
        if tag in ("strong", "b"):
            self._pending_text += "**"
            return
        if tag in ("em", "i"):
            self._pending_text += "_"
            return
        if tag in _BLOCK_TAGS:
            self._hard_break(1)
            return

    def handle_data(self, data: str) -> None:
        self._text(data)

    def handle_entityref(self, name: str) -> None:
        self._text(self.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self._text(self.unescape(f"&#{name};"))

    def handle_comment(self, data: str) -> None:
        return

    def result(self) -> str:
        self._flush_text()
        # Strip leading and trailing empty lines.
        while self._buf and self._buf[-1] == "":
            self._buf.pop()
        while self._buf and self._buf[0] == "":
            self._buf.pop(0)
        # Collapse runs of 3+ blank lines down to 1 blank line.
        out: list[str] = []
        blank_run = 0
        for line in self._buf:
            if line == "":
                blank_run += 1
                if blank_run > 1:
                    continue
            else:
                blank_run = 0
            out.append(line)
        return "\n".join(out)


def html_to_markdown(html: str, base_url: str = "") -> str:
    """Convert `html` to a clean text/markdown-ish string."""
    parser = _HTMLToMarkdown(base_url=base_url)
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, AssertionError) as e:
        logger.debug(f"HTML parser error (non-fatal): {e}")
    return parser.result()


class _LRUCache(OrderedDict):
    """Tiny LRU cache for fetched pages."""

    def __init__(self, max_size: int = 32) -> None:
        super().__init__()
        self._max = max_size

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        if key in self:
            self.move_to_end(key)
            return super().get(key)
        return default

    def put(self, key: str, value: Any) -> None:
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self._max:
            self.popitem(last=False)


class WebFetchTool(Tool):
    """Fetch a URL and return its content as readable markdown."""

    DEFAULT_TIMEOUT_S = 20
    DEFAULT_MAX_CHARS = 50_000
    DEFAULT_CACHE_SIZE = 32
    DEFAULT_CACHE_TTL_S = 300  # 5 min

    def __init__(
        self,
        *,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        max_chars: int = DEFAULT_MAX_CHARS,
        cache_size: int = DEFAULT_CACHE_SIZE,
        cache_ttl_s: int = DEFAULT_CACHE_TTL_S,
        user_agent: str | None = None,
    ) -> None:
        self._timeout_s = _coerce_int(timeout_s, self.DEFAULT_TIMEOUT_S, lo=1, hi=600)
        self._max_chars = _coerce_int(max_chars, self.DEFAULT_MAX_CHARS, lo=100, hi=10_000_000)
        self._cache = _LRUCache(_coerce_int(cache_size, self.DEFAULT_CACHE_SIZE, lo=0))
        self._cache_ttl_s = _coerce_int(cache_ttl_s, self.DEFAULT_CACHE_TTL_S, lo=0)
        self._user_agent = user_agent or (
            "Mozilla/5.0 (compatible; NexusAgent/1.0; +https://github.com/nexus-agent)"
        )

    @property
    def name(self) -> str:
        return "webfetch"

    @property
    def description(self) -> str:
        return (
            "Fetch a URL over HTTP(S) and return its content as readable "
            "markdown. Useful for reading documentation, blog posts, or "
            "API references. Output is capped to ~50KB by default to "
            "protect the LLM context. Cannot execute JavaScript."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "url": {
                "type": "string",
                "description": "Absolute URL to fetch (must be http:// or https://).",
            },
            "max_chars": {
                "type": "integer",
                "description": (
                    f"Maximum characters to return (default {self.DEFAULT_MAX_CHARS}). "
                    "Capped at 10M."
                ),
                "required": False,
            },
            "no_cache": {
                "type": "boolean",
                "description": "If true, bypass the in-memory cache.",
                "required": False,
            },
        }

    @property
    def required_params(self) -> list[str]:
        return ["url"]

    @property
    def permission_level(self) -> str:
        return "read-only"

    @property
    def timeout(self) -> int:
        return self._timeout_s + 5

    def _validate_url(self, url: str) -> str | None:
        if not url or not isinstance(url, str):
            return "Error: URL is required."
        url = url.strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return f"Error: URL scheme must be http or https (got {parsed.scheme!r})."
        if not parsed.netloc:
            return "Error: URL has no host."
        return None

    def _fetch(self, url: str) -> tuple[str, str]:
        """Return (final_url, html). Raises on transport errors."""
        import httpx

        headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        try:
            with httpx.Client(
                timeout=self._timeout_s,
                follow_redirects=True,
                max_redirects=5,
                headers=headers,
            ) as client:
                resp = client.get(url)
        except (httpx.HTTPError, OSError) as e:
            raise RuntimeError(f"HTTP error: {e}") from e

        if resp.status_code >= 400:
            raise RuntimeError(
                f"Server returned HTTP {resp.status_code} for {url}"
            )

        ctype = resp.headers.get("content-type", "").lower()
        if "html" not in ctype and "xml" not in ctype and "text" not in ctype:
            raise RuntimeError(
                f"Unexpected content-type {ctype!r} for {url}; refusing to parse."
            )

        # Decode as utf-8 with a graceful fallback to latin-1
        try:
            html = resp.content.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            html = resp.content.decode("latin-1", errors="ignore")

        return (str(resp.url), html)

    def execute(
        self,
        url: str,
        max_chars: int | None = None,
        no_cache: bool = False,
        **kwargs: Any,
    ) -> str:
        err = self._validate_url(url)
        if err:
            return err
        url = url.strip()
        cap = self._max_chars if max_chars is None else _coerce_int(
            max_chars, self._max_chars, lo=100, hi=10_000_000
        )

        cache_key = f"{url}::{cap}"
        now = time.time()
        if not no_cache and self._cache_ttl_s > 0:
            cached = self._cache.get(cache_key)
            if cached is not None:
                content, ts = cached
                if now - ts < self._cache_ttl_s:
                    return content
                # expired
                self._cache.pop(cache_key, None)

        try:
            final_url, html = self._fetch(url)
        except RuntimeError as e:
            return f"Error fetching {url}: {e}"

        text = html_to_markdown(html, base_url=final_url)

        if len(text) > cap:
            text = text[:cap] + f"\n\n... (truncated at {cap} chars)"

        if self._cache_ttl_s > 0:
            self._cache.put(cache_key, (text, now))

        return text

    def clear_cache(self) -> None:
        self._cache.clear()

    def __repr__(self) -> str:
        return f"<Tool:{self.name} level={self.permission_level} cache={len(self._cache)}>"
