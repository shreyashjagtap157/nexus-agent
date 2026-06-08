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
            
            elif method == "init":
                # Agent is already initialized in run() — just confirm
                self._send_response(req_id, {
                    "session_id": getattr(self._agent, "session_id", "unknown"),
                    "status": "ready",
                })

            elif method == "get_status":
                status = {
                    "session_id": getattr(self._agent, "session_id", "unknown"),
                    "mode": getattr(self._agent, "mode", "unknown"),
                    "effort": getattr(self._agent, "effort_level", "unknown"),
                }
                self._send_response(req_id, status)
            
            elif method == "memory_list":
                memories = self._handle_memory_list(req_id, params)
            
            elif method == "memory_search":
                memories = self._handle_memory_search(req_id, params)
            
            elif method == "memory_stats":
                stats = self._handle_memory_stats(req_id, params)
            
            elif method == "memory_compact":
                self._handle_memory_compact(req_id, params)
            
            elif method == "memory_scores":
                self._handle_memory_scores(req_id, params)
            
            elif method == "get_usage":
                self._handle_get_usage(req_id)
            
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
            for event in self._agent.run_stream(text):
                event_type = event.type.value if hasattr(event.type, 'value') else event.type
                notification = {
                    "jsonrpc": "2.0",
                    "method": "event",
                    "params": {
                        "type": event_type,
                        "data": event.data,
                    }
                }
                sys.stdout.write(json.dumps(notification) + "\n")
                sys.stdout.flush()

                # Emit cost_update after content_complete or done events
                if event_type in ("content_complete", "done"):
                    self._emit_cost_update()

            self._send_response(req_id, {"status": "completed"})

        except Exception as e:
            logger.exception(f"ACP Server: Prompt execution failed: {e}")
            self._send_error(req_id, -32603, f"Execution error: {e}")

    def _emit_cost_update(self) -> None:
        """Emit a cost_update notification with current usage data."""
        try:
            if not hasattr(self._agent, "usage_tracker") or self._agent.usage_tracker is None:
                return
            usage_tracker = self._agent.usage_tracker
            summary = usage_tracker.summarize(session_id=self._agent.session_id)
            cost_data = {
                "estimated_cost": summary.estimated_cost if hasattr(summary, "estimated_cost") else 0.0,
                "total_tokens": summary.total_tokens if hasattr(summary, "total_tokens") else 0,
                "prompt_tokens": summary.prompt_tokens if hasattr(summary, "prompt_tokens") else 0,
                "completion_tokens": summary.completion_tokens if hasattr(summary, "completion_tokens") else 0,
                "entries": summary.entries if hasattr(summary, "entries") else 0,
                "by_model": summary.by_model if hasattr(summary, "by_model") else {},
                "by_session": summary.by_session if hasattr(summary, "by_session") else {},
            }
            cost_notification = {
                "jsonrpc": "2.0",
                "method": "event",
                "params": {
                    "type": "cost_update",
                    "data": cost_data,
                }
            }
            sys.stdout.write(json.dumps(cost_notification) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.debug(f"Failed to emit cost_update: {e}")

    def _get_memory(self):
        """Get the memory manager from the agent."""
        agent = getattr(self, "_agent", None)
        if agent is None:
            return None
        return getattr(agent, "memory", None)

    def _handle_memory_list(self, req_id: Any, params: dict[str, Any]) -> None:
        memory = self._get_memory()
        if memory is None:
            self._send_error(req_id, -32000, "Memory system not available")
            return
        try:
            tier = params.get("tier")
            limit = params.get("limit", 100)
            offset = params.get("offset", 0)
            entries = memory.list_all_unified(tier=tier, limit=limit, offset=offset)
            self._send_response(req_id, {"entries": entries, "count": len(entries)})
        except Exception as e:
            self._send_error(req_id, -32001, f"Memory list failed: {e}")

    def _handle_memory_search(self, req_id: Any, params: dict[str, Any]) -> None:
        memory = self._get_memory()
        if memory is None:
            self._send_error(req_id, -32000, "Memory system not available")
            return
        try:
            query = params.get("query", "")
            limit = params.get("limit", 10)
            results = memory.search(query, limit=limit)
            self._send_response(req_id, {"entries": results, "count": len(results)})
        except Exception as e:
            self._send_error(req_id, -32001, f"Memory search failed: {e}")

    def _handle_memory_stats(self, req_id: Any, params: dict[str, Any]) -> None:
        memory = self._get_memory()
        if memory is None:
            self._send_error(req_id, -32000, "Memory system not available")
            return
        try:
            stats = memory.get_stats()
            self._send_response(req_id, stats)
        except Exception as e:
            self._send_error(req_id, -32001, f"Memory stats failed: {e}")

    def _handle_memory_compact(self, req_id: Any, params: dict[str, Any]) -> None:
        memory = self._get_memory()
        if memory is None:
            self._send_error(req_id, -32000, "Memory system not available")
            return
        try:
            aggressive = params.get("aggressive", False)
            result = memory.compact(aggressive=aggressive)
            self._send_response(req_id, result)
        except Exception as e:
            self._send_error(req_id, -32001, f"Memory compact failed: {e}")

    def _handle_get_usage(self, req_id: Any) -> None:
        """Handle get_usage request — return current cost/usage summary."""
        try:
            if not hasattr(self._agent, "usage_tracker") or self._agent.usage_tracker is None:
                self._send_response(req_id, {
                    "estimated_cost": 0.0,
                    "total_tokens": 0,
                    "entries": 0,
                    "by_model": {},
                    "by_session": {},
                })
                return
            usage_tracker = self._agent.usage_tracker
            summary = usage_tracker.summarize(session_id=self._agent.session_id)
            self._send_response(req_id, {
                "estimated_cost": summary.estimated_cost if hasattr(summary, "estimated_cost") else 0.0,
                "total_tokens": summary.total_tokens if hasattr(summary, "total_tokens") else 0,
                "prompt_tokens": summary.prompt_tokens if hasattr(summary, "prompt_tokens") else 0,
                "completion_tokens": summary.completion_tokens if hasattr(summary, "completion_tokens") else 0,
                "entries": summary.entries if hasattr(summary, "entries") else 0,
                "by_model": summary.by_model if hasattr(summary, "by_model") else {},
                "by_session": summary.by_session if hasattr(summary, "by_session") else {},
            })
        except Exception as e:
            logger.debug(f"get_usage failed: {e}")
            self._send_response(req_id, {
                "estimated_cost": 0.0,
                "total_tokens": 0,
                "entries": 0,
            })

    def _handle_memory_scores(self, req_id: Any, params: dict[str, Any]) -> None:
        memory = self._get_memory()
        if memory is None:
            self._send_error(req_id, -32000, "Memory system not available")
            return
        try:
            scores = memory.get_all_scores()
            self._send_response(req_id, scores)
        except Exception as e:
            self._send_error(req_id, -32001, f"Memory scores failed: {e}")

    def _send_response(self, req_id: Any, result: Any) -> None:
        resp = ACPResponse(id=req_id, result=result)
        sys.stdout.write(resp.to_json() + "\n")
        sys.stdout.flush()

    def _send_error(self, req_id: Any, code: int, message: str) -> None:
        resp = ACPResponse(id=req_id, error={"code": code, "message": message})
        sys.stdout.write(resp.to_json() + "\n")
        sys.stdout.flush()
