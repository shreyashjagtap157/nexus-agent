"""
Agent Client Protocol (ACP) Server — stdio-based JSON-RPC interface.

Allows an external client (like a GUI or another agent) to control
the NexusAgent loop via standard input/output using a JSON-RPC 2.0-like
protocol.

Protocol:
- Request: { "jsonrpc": "2.0", "id": 1, "method": "prompt", "params": { "text": "..." } }
- Response: { "jsonrpc": "2.0", "id": 1, "result": { "content": "...", "usage": { ... } } }
- Notification: { "jsonrpc": "2.0", "method": "event", "params": { "type": "thinking", "content": "..." } }
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class ACPResponse:
    id: Any
    result: Any | None = None
    error: Any | None = None
    jsonrpc: str = "2.0"

    def to_json(self) -> str:
        return json.dumps({
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "result": self.result,
            "error": self.error,
        })


class ACPServer:
    """Stdio-based ACP server that bridges an AgentLoop to a JSON-RPC client."""

    def __init__(
        self,
        agent_factory: Callable[[], Coroutine[Any, Any, Any]],
        workspace: Path | None = None,
    ) -> None:
        self.agent_factory = agent_factory
        self.workspace = workspace or Path.cwd()
        self._agent: Any = None
        self._running = True

    async def run(self) -> None:
        """Main loop reading from stdin and writing to stdout."""
        try:
            # Initialize agent
            self._agent = await self.agent_factory()
            logger.info("ACP Server: Agent initialized and ready.")
        except Exception as e:
            logger.error(f"ACP Server: Failed to initialize agent: {e}")
            return

        # Process stdin line by line
        loop = asyncio.get_event_loop()
        tasks = set()
        while self._running:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                
                # Process each request in a separate task to allow concurrent events
                task = asyncio.create_task(self._handle_request(line))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
            except Exception as e:
                logger.error(f"ACP Server: Error reading stdin: {e}")
                break
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_request(self, line: str) -> None:
        try:
            data = json.loads(line)
            if data.get("jsonrpc") != "2.0":
                self._send_error(None, -32600, "Invalid Request: jsonrpc must be 2.0")
                return

            req_id = data.get("id")
            method = data.get("method")
            params = data.get("params", {})

            if method == "prompt":
                text = params.get("text")
                if not text:
                    self._send_error(req_id, -32602, "Invalid params: 'text' is required")
                    return
                
                # Stream agent events as notifications, and send final result as response
                await self._handle_prompt(req_id, text)
            
            elif method == "get_status":
                status = {
                    "session_id": getattr(self._agent, "session_id", "unknown"),
                    "mode": getattr(self._agent, "mode", "unknown"),
                    "effort": getattr(self._agent, "effort_level", "unknown"),
                }
                self._send_response(req_id, status)
            
            elif method == "stop":
                self._running = False
                self._send_response(req_id, {"status": "stopping"})
            
            else:
                self._send_error(req_id, -32601, f"Method not found: {method}")

        except json.JSONDecodeError:
            self._send_error(None, -32700, "Parse error: Invalid JSON")
        except Exception as e:
            logger.exception(f"ACP Server: Error handling request: {e}")
            self._send_error(req_id if 'req_id' in locals() else None, -32603, f"Internal error: {e}")

    async def _handle_prompt(self, req_id: Any, text: str) -> None:
        """Bridge AgentLoop.run_stream() to ACP events."""
        try:
            # Use run_stream to capture chunks and thinking events
            for event in self._agent.run_stream(text):
                # Emit a JSON-RPC notification for each event
                notification = {
                    "jsonrpc": "2.0",
                    "method": "event",
                    "params": {
                        "type": event.type,
                        "content": event.content if hasattr(event, 'content') else None,
                        "status": event.status if hasattr(event, 'status') else None,
                    }
                }
                sys.stdout.write(json.dumps(notification) + "\n")
                sys.stdout.flush()

            # Final response
            # In a real AgentLoop, the final result is the last response.
            # For simplicity, we just signal completion.
            self._send_response(req_id, {"status": "completed"})

        except Exception as e:
            logger.exception(f"ACP Server: Prompt execution failed: {e}")
            self._send_error(req_id, -32603, f"Execution error: {e}")

    def _send_response(self, req_id: Any, result: Any) -> None:
        resp = ACPResponse(id=req_id, result=result)
        sys.stdout.write(resp.to_json() + "\n")
        sys.stdout.flush()

    def _send_error(self, req_id: Any, code: int, message: str) -> None:
        resp = ACPResponse(id=req_id, error={"code": code, "message": message})
        sys.stdout.write(resp.to_json() + "\n")
        sys.stdout.flush()
