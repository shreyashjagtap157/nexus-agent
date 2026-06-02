"""MCP Transport — Handlers for stdio and SSE communication.

Defines the low-level JSON-RPC 2.0 transport layers for the Model Context Protocol.
"""

from __future__ import annotations

import json
import logging
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class MCPTransport(ABC):
    """Abstract base class for all MCP transports."""

    @abstractmethod
    def start(self) -> None:
        """Start the transport layer."""
        ...

    @abstractmethod
    def send_message(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message."""
        ...

    @abstractmethod
    def register_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a message receiver handler."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Shut down the transport."""
        ...


class StdioTransport(MCPTransport):
    """Standard input/output stream transport for local subprocess MCP connections."""

    def __init__(self, reader=None, writer=None):
        self.reader = reader if reader is not None else sys.stdin
        self.writer = writer if writer is not None else sys.stdout
        self._handler: Callable[[dict[str, Any]], None] | None = None
        self._running = False

    def start(self) -> None:
        self._running = True

    def register_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        self._handler = handler

    def send_message(self, message: dict[str, Any]) -> None:
        """Write JSON-RPC message to stdout stream."""
        try:
            line = json.dumps(message)
            self.writer.write(line + "\n")
            self.writer.flush()
        except (OSError, ValueError) as e:
            logger.error(f"StdioTransport send failure: {e}")

    def listen_loop(self) -> None:
        """Listen for messages on standard input (run in a separate thread)."""
        while self._running:
            try:
                line = self.reader.readline()
                if not line:
                    break

                msg = json.loads(line.strip())
                if self._handler:
                    self._handler(msg)
            except (OSError, ValueError) as e:
                logger.warning(f"StdioTransport read failure: {e}")
                # Don't break — continue listening for valid messages after a bad line

    def close(self) -> None:
        self._running = False
