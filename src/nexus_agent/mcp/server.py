"""MCP Server — Exposes NexusAgent tools to external clients via stdio."""

from __future__ import annotations

import logging
import sys
from typing import Any

from nexus_agent.mcp.transport import StdioTransport

logger = logging.getLogger(__name__)


class MCPServer:
    """Model Context Protocol (MCP) Server.

    Exposes all registered NexusAgent tools to external clients (e.g. Cursor,
    Claude Desktop) over stdio streams using JSON-RPC 2.0.
    """

    def __init__(self, tools: list[Any]):
        """Initialize MCP server.

        Args:
            tools: List of Tool instances to expose.
        """
        self.tools = tools
        self._tool_map = {t.name: t for t in tools}

        self._transport = StdioTransport(reader=sys.stdin, writer=sys.stdout)
        self._transport.register_handler(self._handle_request)

    def start(self) -> None:
        """Start the server and enter listen loop."""
        self._transport.start()
        # Blocks active thread to listen on stdin
        self._transport.listen_loop()

    def _handle_request(self, request: dict[str, Any]) -> None:
        """Process incoming JSON-RPC requests from client."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not req_id:
            # Notifications (no reply)
            return

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {"name": "NexusAgent Server", "version": "1.0"},
                }
                self._send_response(req_id, result)

            elif method == "tools/list":
                tool_list = []
                for t in self.tools:
                    tool_list.append({
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": {
                            "type": "object",
                            "properties": t.parameters,
                            "required": t.required_params,
                        }
                    })
                self._send_response(req_id, {"tools": tool_list})

            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})

                tool = self._tool_map.get(tool_name)
                if not tool:
                    self._send_error(req_id, -32601, f"Tool not found: {tool_name}")
                    return

                # Execute tool
                try:
                    res = tool.execute(**tool_args)
                    self._send_response(req_id, {
                        "content": [
                            {"type": "text", "text": str(res) if res is not None else "Success"}
                        ]
                    })
                except (ValueError, RuntimeError, OSError) as te:
                    self._send_response(req_id, {
                        "isError": True,
                        "content": [
                            {"type": "text", "text": f"Execution error: {te}"}
                        ]
                    })

            else:
                self._send_error(req_id, -32601, f"Method not found: {method}")

        except (ValueError, RuntimeError, OSError) as e:
            logger.exception("MCP Server request processing failure")
            self._send_error(req_id, -32603, f"Internal server error: {e}")

    def _send_response(self, req_id: Any, result: dict[str, Any]) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }
        self._transport.send_message(payload)

    def _send_error(self, req_id: Any, code: int, message: str) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            }
        }
        self._transport.send_message(payload)
