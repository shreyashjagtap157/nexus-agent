"""MCP Client — Connects to external MCP servers and registers their tools."""

from __future__ import annotations

import logging
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from nexus_agent.mcp.transport import StdioTransport
from nexus_agent.tools.base import Tool

logger = logging.getLogger(__name__)


class MCPProxyTool(Tool):
    """A dynamic Tool proxy that executes its action via an external MCP server."""

    def __init__(self, name: str, description: str, parameters: dict[str, Any],
                 required_params: list[str], client: MCPClient):
        super().__init__()
        self._name = name
        self._description = description
        self._parameters = parameters
        self._required_params = required_params
        self._client = client

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    @property
    def required_params(self) -> list[str]:
        return self._required_params

    @property
    def permission_level(self) -> str:
        # Default safety level for external tools (prompt-gated)
        return "ask"

    def execute(self, **kwargs: Any) -> Any:
        """Call the tool on the external MCP server."""
        return self._client.call_tool(self._name, kwargs)


class MCPClient:
    """Model Context Protocol (MCP) Client.

    Spawns and manages external MCP servers, discovering and mapping their
    tools dynamically to expand the agent's capabilities.
    """

    def __init__(self, command: list[str], env: dict[str, str] | None = None):
        """Initialize MCP client.

        Args:
            command: Command array to launch the external MCP server (e.g. ['node', 'server.js']).
            env: Optional environment dictionary overrides.
        """
        # Sanitize command to prevent shell escape or arbitrary command execution
        sanitized_command = []
        allowed_executables = {"node", "npx", "python", "python3", "pip", "pip3", "pipx", "uv", "ruby", "git", "deno"}
        for idx, arg in enumerate(command):
            # Reject any argument containing shell control characters
            if any(char in arg for char in (";", "&", "|", ">", "<", "$", "`", "\n")):
                raise ValueError(f"Dangerous character in MCP command argument: {arg}")

            # If it is the first argument (the executable), ensure it's in the allowlist or is a valid file path
            if idx == 0:
                base_exe = Path(arg).name.lower()
                base_name = base_exe.split(".")[0]
                if base_name not in allowed_executables:
                    path_obj = Path(arg)
                    # Reject if: absolute path not in allowlist, OR non-absolute and doesn't exist
                    if path_obj.is_absolute():
                        # Absolute paths must exist and not be directories
                        if not path_obj.is_file():
                            raise ValueError(f"Absolute path is not a valid executable file: {arg}")
                    else:
                        if not path_obj.exists():
                            raise ValueError(f"Unauthorized or non-existent MCP server executable: {arg}")
            sanitized_command.append(arg)
        self.command = sanitized_command

        # Sanitize and restrict passed environment variables (allowlist)
        allowed_env_keys = {
            "PATH", "HOME", "USER", "LANG", "COMSPEC", "SYSTEMROOT", "WINDIR",
            "TEMP", "TMP", "USERNAME", "USERPROFILE", "LOGNAME", "PWD"
        }
        sanitized_env = {}
        if env:
            for k, v in env.items():
                if k.upper() in allowed_env_keys or k.upper().startswith("NEXUS_") or k.upper().startswith("MCP_"):
                    sanitized_env[k] = v
        self.env = sanitized_env or None

        self._process: subprocess.Popen | None = None
        self._transport: StdioTransport | None = None
        self._lock = threading.Lock()
        self._pending_requests: dict[str, threading.Event] = {}
        self._responses: dict[str, Any] = {}

        self.discovered_tools: list[Tool] = []

    def start(self, startup_timeout: float = 15.0) -> bool:
        """Launch the external MCP server and start listening.

        Args:
            startup_timeout: Maximum seconds to wait for server handshake.

        Returns:
            True if the server was successfully initialized.
        """
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                text=True,
                bufsize=1,
            )

            # Quick check that process started
            ret = self._process.poll()
            if ret is not None:
                logger.error(f"MCP server exited immediately with code {ret}")
                self._process = None
                return False

            self._transport = StdioTransport(
                reader=self._process.stdout,
                writer=self._process.stdin,
            )
            self._transport.register_handler(self._handle_response)
            self._transport.start()

            # Start background reader thread
            threading.Thread(target=self._transport.listen_loop, daemon=True).start()

            # Perform initialize handshake
            if self._initialize(timeout=startup_timeout):
                # Discover tools
                self.discovered_tools = self._list_tools()
                logger.info(f"MCP server initialized. Discovered {len(self.discovered_tools)} tools.")
                return True

            logger.error("MCP server initialization failed, cleaning up")
            self.close()
            return False
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False

    def _send_request(self, method: str, params: dict[str, Any], timeout: float = 15.0) -> Any:
        """Synchronously send JSON-RPC request and wait for the response.

        Args:
            method: JSON-RPC method name.
            params: Method parameters.
            timeout: Maximum seconds to wait for response.

        Returns:
            Result payload.

        Raises:
            TimeoutError: If no response received within timeout.
            RuntimeError: If server returns an error.
        """
        req_id = str(uuid.uuid4())
        event = threading.Event()
        with self._lock:
            self._pending_requests[req_id] = event

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        if self._transport:
            self._transport.send_message(payload)

        # Wait with configurable timeout
        success = event.wait(timeout=timeout)

        with self._lock:
            if req_id in self._pending_requests:
                del self._pending_requests[req_id]

        if not success:
            raise TimeoutError(f"MCP request timed out after {timeout}s: {method}")

        with self._lock:
            response = self._responses.pop(req_id, {})
        if "error" in response:
            raise RuntimeError(f"MCP Server error: {response['error'].get('message', 'Unknown error')}")

        return response.get("result", {})

    def _handle_response(self, message: dict[str, Any]) -> None:
        """Handle incoming JSON-RPC message."""
        req_id = message.get("id")
        if req_id:
            with self._lock:
                if req_id in self._pending_requests:
                    self._responses[req_id] = message
                    self._pending_requests[req_id].set()

    def _initialize(self, timeout: float = 15.0) -> bool:
        """Handshake with the server."""
        try:
            params = {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "NexusAgent", "version": "1.0"},
            }
            res = self._send_request("initialize", params, timeout=timeout)

            # Send initialized notification
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
            if self._transport:
                self._transport.send_message(notification)
            return True
        except (ConnectionError, OSError, ValueError, RuntimeError) as e:
            logger.error(f"Handshake failure: {e}")
            return False

    def _list_tools(self) -> list[Tool]:
        """Request available tools from server."""
        try:
            res = self._send_request("tools/list", {})
            raw_tools = res.get("tools", [])
            tools = []

            for rt in raw_tools:
                schema = rt.get("inputSchema", {})
                tools.append(MCPProxyTool(
                    name=rt["name"],
                    description=rt.get("description", "No description provided"),
                    parameters=schema.get("properties", {}),
                    required_params=schema.get("required", []),
                    client=self,
                ))
            return tools
        except (ValueError, RuntimeError, OSError) as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool call on the remote server."""
        try:
            params = {
                "name": tool_name,
                "arguments": arguments,
            }
            res = self._send_request("tools/call", params)
            content_blocks = res.get("content", [])

            # Extract content blocks text
            text_parts = []
            for cb in content_blocks:
                if cb.get("type") == "text":
                    text_parts.append(cb.get("text", ""))
            return "\n".join(text_parts) if text_parts else "Success (no text output)"
        except (ValueError, RuntimeError, OSError) as e:
            logger.error(f"Failed to execute MCP tool '{tool_name}': {e}")
            raise

    def close(self) -> None:
        """Clean up process and threads with robust termination."""
        if self._transport:
            self._transport.close()
        if self._process:
            try:
                # Try graceful termination first
                self._process.terminate()
                try:
                    self._process.wait(timeout=5.0)  # Increase timeout to 5 seconds
                except subprocess.TimeoutExpired:
                    # Force kill if graceful termination fails
                    logger.warning("MCP server process did not exit gracefully. Killing process tree...")
                    self._process.kill()
                    self._process.wait(timeout=2.0)
            except (OSError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Error terminating MCP process: {e}")
            finally:
                self._process = None
