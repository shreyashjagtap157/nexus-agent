"""Safe declarative MCP configuration API."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from nexus_agent.core.config import load_config, save_user_config


def _secret_env_keys(values: dict[str, str]) -> list[str]:
    markers = ("key", "token", "secret", "password", "credential", "auth")
    return [
        key for key in values
        if any(marker in key.lower() for marker in markers)
    ]


class MCPServerDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    command: str = Field(min_length=1, max_length=4096)
    args: list[str] = Field(default_factory=list, max_length=128)
    env: dict[str, str] = Field(default_factory=dict)
    env_passthrough: list[str] = Field(default_factory=list, max_length=64)
    startup_timeout: float = Field(default=15.0, ge=1.0, le=300.0)
    enabled: bool = True


def register_mcp_routes(app: Any, state_manager: Any) -> None:
    @app.get("/api/mcp")
    async def mcp_config_get(request: Request):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="MCP configuration is restricted to local clients.")
        config = load_config(
            workspace=Path(state_manager.get("workspace") or Path.cwd())
        )
        raw = config.get("mcp", {})
        servers = raw.get("servers", []) if isinstance(raw, dict) else []
        return {
            "servers": servers if isinstance(servers, list) else [],
            "serve": raw.get("serve", {}) if isinstance(raw, dict) else {},
        }

    @app.post("/api/mcp/validate")
    async def mcp_validate(request: Request):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="MCP configuration is restricted to local clients.")
        config = load_config(
            workspace=Path(state_manager.get("workspace") or Path.cwd())
        )
        servers = config.get("mcp", {}).get("servers", [])
        results = []
        for item in servers if isinstance(servers, list) else []:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command") or "")
            valid = bool(command) and not any(
                token in command
                for token in [";", "&&", "||", "|", ">", "<", "$", chr(96)]
            )
            results.append(
                {
                    "name": str(item.get("name") or command),
                    "command": command,
                    "valid": valid,
                    "reason": "safe declarative command" if valid else "shell-control characters detected",
                }
            )
        return {"results": results}

    @app.put("/api/mcp")
    async def mcp_save(request: Request, servers: list[MCPServerDefinition]):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=403, detail="MCP configuration is restricted to local clients.")
        payload = [server.model_dump() for server in servers]
        plaintext_secret_keys = {
            server.name: _secret_env_keys(server.env)
            for server in servers
            if _secret_env_keys(server.env)
        }
        if plaintext_secret_keys:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Secret-like environment values must use env_passthrough.",
                    "servers": plaintext_secret_keys,
                },
            )
        save_user_config({"mcp": {"servers": payload}})
        return {"saved": True, "count": len(payload)}
