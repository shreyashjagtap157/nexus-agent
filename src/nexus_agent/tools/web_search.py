"""
Web Search Tool — Search the internet when online.
"""

from __future__ import annotations

import logging
from typing import Any

from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)


class WebSearchTool(Tool):
    """Search the web for information (requires internet connection)."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for information. Uses DuckDuckGo search. "
            "Only works when the agent has internet connectivity. "
            "Returns search results with titles, URLs, and snippets."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 5)",
                "required": False,
            },
        }

    @property
    def permission_level(self) -> str:
        return "read-only"

    @property
    def timeout(self) -> int:
        return 30

    def execute(self, query: str, max_results: int = 5, **kwargs: Any) -> str:
        # Validate query length
        if len(query) < 1:
            return "Error: Query cannot be empty."
        if len(query) >= 512:
            return "Error: Query exceeds maximum length of 512 characters."

        try:
            import httpx

            # Use DuckDuckGo Instant Answer API (no API key needed)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NexusAgent/1.0"}
            response = httpx.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1"},
                headers=headers,
                timeout=self.timeout,
            )
            data = response.json()

            results: list[str] = []

            # Abstract (main answer)
            if data.get("Abstract"):
                results.append(f"**{data.get('Heading', 'Result')}**")
                results.append(data["Abstract"])
                if data.get("AbstractURL"):
                    results.append(f"Source: {data['AbstractURL']}")
                results.append("")

            # Recursively iterate related topics including nested category Topics
            def process_topics(topics: list, depth: int = 0) -> None:
                for topic in topics[:max_results - len(results)]:
                    if len(results) >= max_results:
                        break
                    if isinstance(topic, dict):
                        if "Text" in topic:
                            text = topic["Text"]
                            url = topic.get("FirstURL", "")
                            results.append(f"• {text}")
                            if url:
                                results.append(f"  URL: {url}")
                        # Recursively process nested Topics
                        if "Topics" in topic and isinstance(topic["Topics"], list):
                            process_topics(topic["Topics"], depth + 1)

            process_topics(data.get("RelatedTopics", []))

            if not results:
                return f"No results found for: {query}"

            return "\n".join(results)

        except ImportError:
            return "Error: httpx library not available for web search"
        except (OSError, ValueError) as e:
            logger.error(f"Web search error: {e}")
            return f"Error performing web search: {e}"
