"""Browser automation tool — headless browser and HTML scraper for web interaction.

The Playwright executable path, user data directory, and timeout are now all
configurable via env vars or the ``BrowserConfig`` dataclass, so the tool no
longer depends on a hard-coded install location. Configuration precedence:

  1. Constructor argument (``BrowserConfig``)
  2. Environment variable (NEXUS_BROWSER_*)
  3. Auto-detected default
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)

PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
]

CLOUD_METADATA_IPS = {
    "169.254.169.254",  # AWS/GCP/Azure
    "100.100.100.200",  # Alibaba
    "192.0.0.192",      # Oracle
}

DISALLOWED_HOST_PATTERNS = [
    re.compile(r"^metadata\.google\.internal$", re.IGNORECASE),
    re.compile(r"^metadata$", re.IGNORECASE),
]


@dataclass
class BrowserConfig:
    """Runtime configuration for ``BrowserTool``.

    Attributes:
        executable_path: Absolute path to a Chromium-family binary. When
            ``None`` we let Playwright auto-discover.
        user_data_dir: Persistent profile directory. Falls back to a temp dir
            when ``None`` so multiple BrowserTool instances do not collide.
        screenshot_dir: Where to write screenshots. Defaults to
            ``.nexus-agent/screenshots`` under the workspace.
        navigation_timeout_ms: Page navigation timeout in milliseconds.
        user_agent: Custom User-Agent string.
        extra_launch_args: Extra Chromium command-line flags (e.g. for sandboxing).
    """

    executable_path: str | None = None
    user_data_dir: Path | None = None
    screenshot_dir: Path | None = None
    navigation_timeout_ms: int = 15000
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NexusAgent/1.0"
    extra_launch_args: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls, workspace: Path | None = None) -> "BrowserConfig":
        """Build a config from ``NEXUS_BROWSER_*`` environment variables.

        Recognised vars:
            NEXUS_BROWSER_EXECUTABLE       — path to chromium/chrome
            NEXUS_BROWSER_USER_DATA_DIR    — persistent profile dir
            NEXUS_BROWSER_SCREENSHOT_DIR   — output dir for screenshots
            NEXUS_BROWSER_TIMEOUT_MS       — nav timeout override
        """
        exe = os.environ.get("NEXUS_BROWSER_EXECUTABLE")
        udd = os.environ.get("NEXUS_BROWSER_USER_DATA_DIR")
        sd = os.environ.get("NEXUS_BROWSER_SCREENSHOT_DIR")
        to = os.environ.get("NEXUS_BROWSER_TIMEOUT_MS")
        workspace = workspace or Path.cwd()
        screenshot_dir = Path(sd) if sd else workspace / ".nexus-agent" / "screenshots"
        return cls(
            executable_path=exe,
            user_data_dir=Path(udd) if udd else None,
            screenshot_dir=screenshot_dir,
            navigation_timeout_ms=int(to) if to and to.isdigit() else 15000,
        )


def _resolve_browser_executable(configured: str | None) -> str | None:
    """Resolve a Chromium-family binary.

    Order of preference:
        1. Caller-supplied path
        2. ``$NEXUS_BROWSER_EXECUTABLE``
        3. ``shutil.which`` for ``chromium``, ``chromium-browser``,
           ``google-chrome``, ``chrome``, ``msedge``
    """
    if configured:
        if os.path.isabs(configured) and os.path.exists(configured):
            return configured
        resolved = shutil.which(configured)
        if resolved:
            return resolved
        logger.warning("Configured browser path %r not found; falling back to auto-detect.",
                       configured)

    for name in ("chromium", "chromium-browser", "google-chrome", "chrome", "msedge"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


class BrowserTool(Tool):
    """Browser automation and web crawling scraper.

    Uses Playwright for headless interactive sessions if available.
    Falls back to a high-speed async HTTPX and HTML parser that converts pages
    into clean Markdown for LLM consumption, ensuring maximum offline/online resilience.
    """

    MAX_CONTENT_LENGTH = 4000

    def __init__(self, workspace: Path | None = None,
                 config: BrowserConfig | None = None):
        self.workspace = workspace or Path.cwd()
        self.config = config or BrowserConfig.from_env(self.workspace)
        # Lazy: a per-instance data dir if the user did not provide one
        self._owns_data_dir = self.config.user_data_dir is None
        self._temp_data_dir: tempfile.TemporaryDirectory | None = None
        if self._owns_data_dir:
            self._temp_data_dir = tempfile.TemporaryDirectory(prefix="nexus_browser_")
            self.config.user_data_dir = Path(self._temp_data_dir.name)

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "Interact with web pages, search resources, and scrape articles. "
            "Supports: navigate to URL, read page content, click elements, and take screenshots. "
            "Runs Playwright if installed; falls back to an elegant HTTPX Markdown converter. "
            "The browser executable, profile dir, and timeout are configurable via "
            "BrowserConfig or NEXUS_BROWSER_EXECUTABLE / NEXUS_BROWSER_USER_DATA_DIR / "
            "NEXUS_BROWSER_TIMEOUT_MS env vars."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "Browser action: 'navigate', 'read', 'click', 'screenshot'",
                "enum": ["navigate", "read", "click", "screenshot"],
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to",
                "required": False,
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for click/read actions",
                "required": False,
            },
            "output_path": {
                "type": "string",
                "description": "Optional path for the screenshot file (action='screenshot')",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-write"

    @staticmethod
    def _safe_truncate(text: str, max_length: int) -> str:
        """Truncate text at a safe UTF-8 character boundary."""
        if len(text) <= max_length:
            return text
        # Find a safe truncation point by backing up to the last space
        truncated = text[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > max_length // 2:
            return truncated[:last_space] + "..."
        return truncated + "..."

    @staticmethod
    def _validate_url(url: str) -> str | None:
        """Validate URL for SSRF and security concerns. Returns error message or None."""
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        host = parsed.hostname

        if scheme == "file":
            return "Error: file:// URLs are not allowed."

        if scheme not in ("http", "https"):
            return f"Error: Unsupported URL scheme '{scheme}'."

        # Resolve host to IP
        try:
            import socket
            addr = socket.getaddrinfo(host, None)[0][4][0]
        except (OSError, ValueError):
            return f"Error: Cannot resolve hostname '{host}'."

        # Block cloud metadata IPs
        if addr in CLOUD_METADATA_IPS:
            return f"Error: Access to cloud metadata IP '{addr}' is blocked."

        # Block private/reserved IPs
        try:
            ip = ipaddress.ip_address(addr)
            if any(ip in net for net in PRIVATE_NETWORKS):
                return f"Error: Access to private IP '{addr}' is blocked."
        except ValueError:
            return f"Error: Invalid IP address '{addr}'."

        # Block known metadata hostnames
        for pat in DISALLOWED_HOST_PATTERNS:
            if host and pat.search(host):
                return f"Error: Access to hostname '{host}' is blocked."

        return None

    def execute(self, action: str, url: str = "", selector: str = "",
                 output_path: str = "", **kwargs: Any) -> str:
        if action == "navigate" and not url:
            return "Error: A valid target URL is required for navigation."

        # Validate URL for SSRF protection
        if url:
            err = self._validate_url(url)
            if err:
                return err

        # 1. Try Playwright headless automation
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
            return self._execute_playwright(action, url, selector, output_path)
        except ImportError:
            logger.info("Playwright not installed. Falling back to HTTPX scraper.")

        # 2. HTTPX & HTML static parser fallback
        try:
            return self._execute_httpx(action, url)
        except (OSError, ValueError) as e:
            return f"Failed to execute browser fallback scraping: {e}"

    def _ensure_browser(self) -> None:
        """Initialize the persistent Playwright headless browser context if not already active."""
        if self._playwright is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()

            launch_kwargs: dict[str, Any] = {
                "headless": True,
                "args": list(self.config.extra_launch_args),
            }
            resolved_exe = _resolve_browser_executable(self.config.executable_path)
            if resolved_exe:
                launch_kwargs["executable_path"] = resolved_exe
            self._browser = self._playwright.chromium.launch(**launch_kwargs)

            if self.config.user_data_dir:
                self.config.user_data_dir.mkdir(parents=True, exist_ok=True)

            self._context = self._browser.new_context(
                user_agent=self.config.user_agent,
                viewport={"width": 1280, "height": 800},
            )
            self._context.set_default_navigation_timeout(self.config.navigation_timeout_ms)
            self._context.set_default_timeout(self.config.navigation_timeout_ms)
            self._page = self._context.new_page()

    def _execute_playwright(self, action: str, url: str, selector: str,
                             output_path: str) -> str:
        try:
            self._ensure_browser()
            assert self._page is not None
            page = self._page

            if action == "navigate":
                page.goto(url, wait_until="networkidle")
                title = page.title()
                text = page.locator("body").inner_text()
                clean_text = self._clean_markdown(text)
                return f"### Webpage: {title}\nURL: {url}\n\nContent:\n{self._safe_truncate(clean_text, self.MAX_CONTENT_LENGTH)}"

            elif action == "read":
                if not url:
                    return "Error: Navigation URL required to read."
                page.goto(url, wait_until="domcontentloaded")
                if selector:
                    content = page.locator(selector).first.inner_text()
                    return f"### Content under selector '{selector}':\n{self._safe_truncate(content, self.MAX_CONTENT_LENGTH)}"
                text = page.locator("body").inner_text()
                return self._safe_truncate(self._clean_markdown(text), self.MAX_CONTENT_LENGTH)

            elif action == "click":
                if not url:
                    return "Error: Navigation URL required to click elements."
                page.goto(url, wait_until="domcontentloaded")
                if not selector:
                    return "Error: CSS selector is required for click action."
                target = page.locator(selector).first
                target.click(timeout=5000)
                page.wait_for_timeout(2000)
                new_url = page.url
                return f"Successfully clicked '{selector}'! Navigated to: {new_url}"

            elif action == "screenshot":
                if not url:
                    return "Error: Navigation URL required for screenshot."
                page.goto(url, wait_until="networkidle")

                if output_path:
                    target_file = Path(output_path).expanduser().resolve()
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                else:
                    shot_dir = self.config.screenshot_dir or (self.workspace / ".nexus-agent" / "screenshots")
                    shot_dir.mkdir(parents=True, exist_ok=True)
                    target_file = shot_dir / "web_capture.png"

                page.screenshot(path=str(target_file))
                return f"✅ Headless screenshot captured and saved successfully to: {target_file}"

        except (OSError, ValueError, RuntimeError) as e:
            return f"Browser execution error: {e}"

        return "Action completed."

    def _execute_httpx(self, action: str, url: str) -> str:
        from html.parser import HTMLParser

        import httpx

        if action in ("click", "screenshot"):
            return (f"Action '{action}' requires headless browser engines. "
                    f"Install Playwright with `pip install playwright && playwright install`, "
                    f"or set NEXUS_BROWSER_EXECUTABLE to a Chromium binary on disk.")

        if not url:
            return "Error: A valid target URL is required."

        # Fetch using HTTPX - do NOT follow redirects automatically (SSRF protection)
        # Manually follow redirects and re-validate each target
        import socket

        def is_private_url(target_url: str) -> bool:
            try:
                parsed = httpx.URL(target_url)
                host = parsed.host
                if not host:
                    return True
                addr = socket.gethostbyname(host)
                ip = ipaddress.ip_address(addr)
                return ip.is_private or ip.is_loopback or ip.is_reserved
            except (ValueError, OSError):
                return True  # Block on any resolution failure

        client = httpx.Client(timeout=10.0, follow_redirects=False)
        try:
            headers = {"User-Agent": self.config.user_agent}
            res = client.get(url, headers=headers)
            # Manually follow redirects with validation
            max_redirects = 5
            redirect_count = 0
            while res.status_code in (301, 302, 303, 307, 308) and redirect_count < max_redirects:
                location = res.headers.get("location", "")
                if not location:
                    break
                next_url = httpx.URL(url).join(httpx.URL(location)).unicode_string()
                if is_private_url(next_url):
                    return f"Error: Redirect to private/reserved IP blocked: {next_url}"
                url = next_url
                res = client.get(url, headers=headers)
                redirect_count += 1
            html_content = res.text
        finally:
            client.close()

        # Custom HTML parser to strip tags and extract format-text
        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text_blocks = []
                self.in_script_or_style = False

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                if tag in ("script", "style"):
                    self.in_script_or_style = True
                elif tag in ("p", "h1", "h2", "h3", "h4", "li", "tr", "div", "section", "article"):
                    self.text_blocks.append("\n")
                elif tag == "br":
                    self.text_blocks.append("\n")
                elif tag == "td":
                    self.text_blocks.append(" | ")

            def handle_endtag(self, tag: str) -> None:
                if tag in ("script", "style"):
                    self.in_script_or_style = False

            def handle_data(self, data: str) -> None:
                if not self.in_script_or_style:
                    clean_data = data.strip()
                    if clean_data:
                        self.text_blocks.append(clean_data + " ")

            def get_text(self) -> str:
                return "".join(self.text_blocks)

        parser = TextExtractor()
        parser.feed(html_content)
        extracted = parser.get_text()
        clean = self._clean_markdown(extracted)

        return f"### Webpage Scraped (Fallback Mode): {url}\n\nContent:\n{self._safe_truncate(clean, self.MAX_CONTENT_LENGTH)}"

    def _clean_markdown(self, text: str) -> str:
        """Strip duplicate spacing and empty lines, collapse multiple blank lines."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        # Collapse multiple consecutive blank lines
        result = []
        prev_blank = False
        for line in lines:
            if not line:
                if not prev_blank:
                    result.append(line)
                prev_blank = True
            else:
                result.append(line)
                prev_blank = False
        return "\n".join(result)

    def close(self) -> None:
        """Clean up active browser instance and Playwright drivers."""
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except (OSError, RuntimeError):
            pass
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            if self._temp_data_dir is not None:
                try:
                    self._temp_data_dir.cleanup()
                except (OSError, ValueError):
                    pass
                self._temp_data_dir = None

    def __del__(self) -> None:
        try:
            self.close()
        except (OSError, RuntimeError):
            pass
