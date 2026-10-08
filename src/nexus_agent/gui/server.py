"""
FastAPI GUI Server for NexusAgent.

Provides a local async web server with WebSocket streaming for the premium
web-based dashboard, allowing real-time LLM interaction and agent control.
"""

from __future__ import annotations

import asyncio
import json
import os
import logging
import socket
import subprocess
import threading
import time
import webbrowser
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from nexus_agent import __app_name__, __version__
from nexus_agent.agents.web_routes import register_agent_routes
from nexus_agent.audit.web_routes import register_audit_routes
from nexus_agent.mcp.web_routes import register_mcp_routes
from nexus_agent.mcp.client import load_configured_servers
from nexus_agent.skills.web_routes import register_skill_routes
from nexus_agent.auth.web_routes import register_auth_routes
from nexus_agent.research.web_routes import register_research_source_routes
from nexus_agent.memory.web_routes import register_memory_routes
from nexus_agent.core.agent import AgentEvent, AgentLoop, AgentLoopConfig, AgentMode
from nexus_agent.core.config import load_config, save_user_config, _strip_secrets
from nexus_agent.core.debate import DebateEngine
from nexus_agent.core.devops import VerificationPipeline
from nexus_agent.core.nla_telemetry import NLATelemetry
from nexus_agent.core.task_graph import TaskGraph
from nexus_agent.core.usage import UsageTracker
from nexus_agent.llm.local_engine import LocalEngine
from nexus_agent.llm.model_manager import ModelManager
from nexus_agent.llm.providers.factory import ProviderFactory
from nexus_agent.llm.runtime_manager import RuntimeManager
from nexus_agent.memory.memory_manager import MemoryManager
from nexus_agent.permissions.manager import PermissionManager
from nexus_agent.session.manager import SessionManager
from nexus_agent.storage.layout import StorageLayout
from nexus_agent.tools.code_edit import CodeEditTool, InsertLinesTool
from nexus_agent.tools.file_ops import (
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from nexus_agent.tools.git_ops import GitTool, SmartCommitTool
from nexus_agent.tools.memory import MemoryTool
from nexus_agent.tools.shell import ShellTool
from nexus_agent.tools.todowrite import TodoWriteTool
from nexus_agent.tools.web_search import WebSearchTool
from nexus_agent.tools.webfetch import WebFetchTool
from nexus_agent.team.web_routes import register_team_routes

logger = logging.getLogger(__name__)


class StateManager:
    """Thread-safe wrapper around a shared state dict."""

    def __init__(self, initial: dict | None = None):
        self._lock = threading.Lock()
        self._state = initial or {}

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._state[key] = value


# Global instances shared across endpoints
state_manager = StateManager({
    "config": {},
    "workspace": Path.cwd(),
    "runtime_manager": None,
    "memory_manager": None,
    "session_manager": None,
    "permission_manager": None,
    "active_session_id": None,
    "engine": None,
    "web_agent_threads": {},
    "web_agent_lock": threading.RLock(),
})


def _require_local_client(request: Request) -> None:
    host = request.client.host if request.client else None
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=403, detail="State-changing GUI access is restricted to local clients.")


def get_free_port() -> int:
    """Get a free port on localhost."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


app = FastAPI(
    title=__app_name__,
    description="Offline-First LLM Coding Agent Web Interface",
    version=__version__,
)

# Unified multi-agent team API shares the existing provider, workspace and permission state.
register_team_routes(app, state_manager)
register_agent_routes(app, state_manager)
register_audit_routes(app, state_manager)
register_mcp_routes(app, state_manager)
register_skill_routes(app, state_manager)
register_auth_routes(app, state_manager)
register_research_source_routes(app, state_manager)
register_memory_routes(app, state_manager)

# Rate limiting store
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = asyncio.Lock()
RATE_LIMIT_MAX = 100
RATE_LIMIT_WINDOW = 60.0
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Combined security middleware: rate limiting, body size check, and CSP headers."""
    # Rate limiting by client IP
    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW
        async with _rate_limit_lock:
            hits = _rate_limit_store[client_ip]
            _rate_limit_store[client_ip] = [t for t in hits if t > window_start]
            if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX:
                return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})
            _rate_limit_store[client_ip].append(now)

        # Request body size limit
        content_length = request.headers.get("content-length")
        try:
            if content_length and int(content_length) > MAX_BODY_SIZE:
                return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        except (ValueError, TypeError):
            pass

    response = await call_next(request)
    # CSP headers
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' ws:; "
        "font-src 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# Enable CORS for local development only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request bodies
class ModelLoadRequest(BaseModel):
    model_path: Annotated[str, Field(max_length=1024)]
    gpu_layers: int | None = None
    context_size: int | None = None
    threads: int | None = None
    flash_attention: bool | None = None
    unified_kv_cache: bool | None = None
    kv_quant_type: Annotated[str | None, Field(max_length=32)] = None


class ConfigUpdateRequest(BaseModel):
    effort_level: Annotated[str | None, Field(max_length=256)] = None
    goal: Annotated[str | None, Field(max_length=256)] = None
    guardrails: Annotated[str | None, Field(max_length=256)] = None


class GeneralConfigUpdateRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class SessionCreateRequest(BaseModel):
    title: Annotated[str | None, Field(max_length=256)] = None



def _merge_user_section(section: str, values: dict[str, Any]) -> dict[str, Any]:
    allowed_sections = {
        "agent", "research", "team", "local_model", "permissions", "gui", "session",
        "skills", "mcp", "cli", "memory",
    }
    if section not in allowed_sections:
        raise HTTPException(status_code=400, detail="Configuration section is not editable from the web UI.")
    clean = _strip_secrets(values)
    if section in {"agent", "research", "team", "local_model", "permissions", "gui", "session", "skills", "mcp", "cli", "memory"}:
        save_user_config({section: clean})
        cfg = state_manager.get("config")
        cfg[section] = {**cfg.get(section, {}), **clean}
        state_manager.set("config", cfg)
        return cfg[section]
    raise HTTPException(status_code=400, detail="Unsupported configuration section.")


@app.get("/api/config/full")
async def get_full_config(request: Request):
    """Return effective configuration with credentials and private keys stripped."""
    _require_local_client(request)
    return _strip_secrets(state_manager.get("config") or {})


@app.put("/api/config/{section}")
async def update_config_section(section: str, req: GeneralConfigUpdateRequest, request: Request):
    """Update one editable user configuration section from a local client."""
    _require_local_client(request)
    return {"success": True, "section": section, "config": _merge_user_section(section, req.values)}


# --- API ENDPOINTS ---

@app.get("/api/status")
async def get_status(request: Request):
    """Get status of the agent core."""
    _require_local_client(request)
    engine = state_manager.get("engine")
    model_name = engine.model_name if (engine and engine.is_loaded) else "No model loaded"
    runtime = state_manager.get("config").get("local_model", {}).get("runtime", "auto")
    gpu_backend = state_manager.get("config").get("local_model", {}).get("gpu_backend", "auto")

    # Hardware status
    mgr = ModelManager()
    hw_info = mgr.detect_hardware()

    ram_info = psutil.virtual_memory()
    is_loaded = getattr(engine, "is_loaded", True) if engine else False

    return {
        "app_name": __app_name__,
        "version": __version__,
        "model_loaded": is_loaded,
        "model_name": model_name,
        "runtime": runtime,
        "gpu_backend": gpu_backend,
        "workspace": str(state_manager.get("workspace")),
        "active_session_id": state_manager.get("active_session_id"),
        "hardware": {
            "cpu": hw_info.get("cpu"),
            "ram_total": hw_info.get("ram_total"),
            "ram_available": hw_info.get("ram_available"),
            "ram_percent": ram_info.percent,
            "gpu": hw_info.get("gpu"),
            "vram": hw_info.get("vram"),
            "npu": hw_info.get("npu"),
            "recommended": hw_info.get("recommended_model_size"),
        }
    }


@app.get("/api/models")
async def get_models(request: Request):
    """List discovered models in standard GGUF and ONNX formats."""
    _require_local_client(request)
    local_config = state_manager.get("config").get("local_model", {})
    mgr = ModelManager(models_dir=local_config.get("models_dir"))
    models = mgr.discover_models()

    # Format list
    serialized = []
    for m in models:
        serialized.append({
            "name": m["name"],
            "filename": m["filename"],
            "path": str(m["path"]),
            "size_str": m["size_str"],
            "quantization": m.get("quantization", "unknown"),
            "format": m.get("format", "gguf"),
        })
    return serialized


@app.post("/api/models/load")
async def load_model(req: ModelLoadRequest, request: Request):
    """Load a model using local engine fine-tuning settings & guardrails."""
    _require_local_client(request)
    try:
        # Check guardrails first
        guardrail_level = state_manager.get("config").get("local_model", {}).get("guardrails", "balanced")
        mgr = ModelManager()
        chk = mgr.evaluate_loading_guardrail(req.model_path, guardrail_level)
        if not chk["allowed"]:
            raise HTTPException(status_code=400, detail=chk["warning"])

        # Construct loading parameters with dynamic settings
        load_kwargs: dict[str, Any] = {}
        if req.gpu_layers is not None: load_kwargs["gpu_layers"] = req.gpu_layers
        if req.context_size is not None: load_kwargs["context_size"] = req.context_size
        if req.threads is not None: load_kwargs["threads"] = req.threads
        if req.flash_attention is not None: load_kwargs["flash_attention"] = req.flash_attention
        if req.unified_kv_cache is not None: load_kwargs["unified_kv_cache"] = req.unified_kv_cache
        if req.kv_quant_type is not None: load_kwargs["kv_quant_type"] = req.kv_quant_type

        # Select and swap active LocalEngine — close previous engine first
        old_engine = state_manager.get("engine")
        engine = LocalEngine(
            model_path=req.model_path,
            **load_kwargs
        )
        state_manager.set("engine", engine)
        if old_engine is not None:
            try:
                old_engine.close()
            except (OSError, RuntimeError):
                pass

        warning_msg = chk.get("warning")
        return {
            "success": True,
            "message": f"Successfully loaded model: {engine.model_name}",
            "model_name": engine.model_name,
            "warning": warning_msg,
        }
    except HTTPException:
        raise
    except (ValueError, RuntimeError, OSError):
        logger.exception("Failed to load model")
        raise HTTPException(status_code=500, detail="Internal server error loading model")


@app.post("/api/config/update")
async def update_config(req: ConfigUpdateRequest, request: Request):
    """Update active configuration values dynamically."""
    _require_local_client(request)
    if req.effort_level is not None:
        state_manager.get("config").setdefault("agent", {})["effort_level"] = req.effort_level
    if req.goal is not None:
        state_manager.get("config").setdefault("agent", {})["goal"] = req.goal
    if req.guardrails is not None:
        state_manager.get("config").setdefault("local_model", {})["guardrails"] = req.guardrails
    return {"success": True, "config": state_manager.get("config")}


@app.get("/api/activity/files")
async def file_activity(request: Request, limit: int = 250):
    _require_local_client(request)
    from nexus_agent.storage.journal import FileJournal
    workspace = Path(state_manager.get("workspace") or Path.cwd()).resolve()
    journal = FileJournal(StorageLayout(workspace).workspace_runtime / "file-journal.db")
    try:
        return {"changes": journal.recent(limit)}
    finally:
        journal.close()


@app.get("/api/sessions")
async def list_sessions(request: Request):
    """List saved conversation sessions."""
    _require_local_client(request)
    sm = state_manager.get("session_manager")
    if not sm:
        return []
    return sm.list_sessions()


@app.post("/api/sessions/create")
async def create_session(req: SessionCreateRequest, request: Request):
    """Create a new conversation session."""
    _require_local_client(request)
    sm = state_manager.get("session_manager")
    if not sm:
        raise HTTPException(status_code=500, detail="SessionManager not initialized")

    engine = state_manager.get("engine")
    is_loaded = getattr(engine, "is_loaded", True) if engine else False
    model_name = engine.model_name if (engine and is_loaded) else "no-model"
    provider_name = engine.name if engine else "local"

    session_id = sm.create_session(
        model=model_name,
        provider=provider_name,
        workspace=str(state_manager.get("workspace")),
    )
    state_manager.set("active_session_id", session_id)

    if req.title:
        sm.storage.update_session_title(session_id, req.title)

    return {"session_id": session_id, "title": sm.list_sessions()[0].get("title", "New Session")}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    """Get history of a conversation session."""
    _require_local_client(request)
    sm = state_manager.get("session_manager")
    if not sm:
        raise HTTPException(status_code=500, detail="SessionManager not initialized")

    history = sm.storage.get_messages(session_id)
    return {
        "session_id": session_id,
        "messages": history,
    }


@app.get("/api/tasks")
async def get_tasks(request: Request):
    """Get the current state of the hierarchical task graph."""
    _require_local_client(request)
    session_id = state_manager.get("active_session_id")
    if not session_id:
        return {"error": "No active session"}
    tg = TaskGraph(session_id=session_id, workspace=state_manager.get("workspace"))
    if tg.load():
        return {
            "session_id": session_id,
            "root_id": tg.root_id,
            "progress": tg.get_progress(),
            "nodes": {nid: node.to_dict() for nid, node in tg.nodes.items()},
            "markdown": tg.to_markdown()
        }
    return {"message": "No active task graph for this session."}


@app.get("/api/nla/{session_id}")
async def get_nla(session_id: str, request: Request):
    """Retrieve NLA reasoning logs and autoencoder telemetry summary."""
    _require_local_client(request)
    nla = NLATelemetry(session_id=session_id, workspace=state_manager.get("workspace"))
    records = nla.load_records()
    return {
        "session_id": session_id,
        "records": [r.to_dict() for r in records],
        "summary": nla.generate_session_summary()
    }


@app.post("/api/debate")
async def trigger_debate(request: Request):
    """Convening parallel code debate reviews."""
    _require_local_client(request)
    try:
        diff_res = subprocess.run(["git", "diff", "HEAD"], cwd=str(state_manager.get("workspace")), capture_output=True, text=True, timeout=10)
        changes = diff_res.stdout or "Simulated: refactoring core pipeline structures"
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        logger.debug(f"Git diff failed, using simulated changes: {e}")
        changes = "Simulated: refactoring core pipeline structures"

    engine = DebateEngine(provider=state_manager.get("engine"))
    verdict = engine.run_debate(code_changes=changes)
    return {
        "consensus_score": verdict.consensus_score,
        "final_approved": verdict.final_approved,
        "scores": verdict.reviewer_scores,
        "summary": verdict.consensus_summary,
        "issues": verdict.aggregated_issues,
        "recommendations": verdict.recommendations
    }


@app.post("/api/verify")
async def trigger_verify(request: Request):
    """Execute static lint and test framework pipeline validation."""
    _require_local_client(request)
    pipeline = VerificationPipeline(workspace=state_manager.get("workspace"))
    report = pipeline.run_full_pipeline()
    return {
        "success": report.success,
        "test_framework": report.test_framework_detected,
        "tests_passed": report.tests_passed,
        "linters_passed": report.linters_passed,
        "secrets_found": [
            {"file": s.file_path, "line": s.line_number, "pattern": s.pattern_name}
            for s in report.secrets_found
        ],
        "vulnerabilities": report.vulnerabilities_found,
        "traceback_analysis": report.traceback_analysis
    }


@app.post("/api/commit")
async def trigger_commit(request: Request):
    """Auto-generate conventional commits from staged modifications."""
    _require_local_client(request)
    tool = SmartCommitTool(workspace=state_manager.get("workspace"), provider=state_manager.get("engine"))
    msg = tool.execute()
    return {"message": msg}


# --- WEBSOCKET REAL-TIME STREAMING ---

@app.websocket("/api/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket connection for real-time chat streaming and agent logs."""
    host = websocket.client.host if websocket.client else None
    if host not in {"127.0.0.1", "::1", "localhost"}:
        await websocket.close(code=1008, reason="Agent WebSocket access is restricted to local clients.")
        return
    await websocket.accept()
    logger.info(f"WebSocket client connected for session: {session_id}")
    state_manager.set("active_session_id", session_id)

    try:
        while True:
            # Wait for user input prompt
            data_str = await websocket.receive_text()
            if len(data_str) > 65536:
                await websocket.send_json({"type": "error", "content": "Message exceeds 64 KiB limit."})
                continue
            data = json.loads(data_str)
            prompt = data.get("prompt", "").strip()
            mode_str = data.get("mode", "auto").lower()

            if not prompt:
                continue

            with state_manager.get("web_agent_lock"):
                active_threads = state_manager.get("web_agent_threads")
                running_thread = active_threads.get(session_id)
                if running_thread is not None and running_thread.is_alive():
                    await websocket.send_json({
                        "type": "error",
                        "content": "A response is already running for this session. Wait for completion before sending another prompt.",
                    })
                    continue
                active_threads[session_id] = None

            # Auto-title session if first message
            sm = state_manager.get("session_manager")
            if sm:
                sm.auto_title(prompt)
                sm.save_message("user", content=prompt, type="user")

            # Check model loading
            engine = state_manager.get("engine")
            is_loaded = getattr(engine, "is_loaded", True) if engine else False
            if not engine or not is_loaded:
                await websocket.send_json({
                    "type": "error",
                    "content": "No model loaded. Please load a model or configure a provider first."
                })
                await websocket.send_json({"type": "done", "iterations": 0})
                continue


            # Prepare the same comprehensive workspace tool catalog used by
            # the CLI/TUI and multi-agent runtime, plus configured MCP proxies.
            from nexus_agent.team.runtime import build_workspace_tools
            config = state_manager.get("config") or {}
            mcp_clients, mcp_tools = load_configured_servers(config)
            tools = build_workspace_tools(
                Path(state_manager.get("workspace")),
                memory_manager=state_manager.get("memory_manager"),
                provider=engine,
                mcp_tools=mcp_tools,
            )

            # Build memory prompt context
            memory_context = ""
            if state_manager.get("memory_manager"):
                memory_context = state_manager.get("memory_manager").get_context_for_prompt()

            # Instantiate AgentLoop
            agent_cfg = AgentLoopConfig(
                mode=AgentMode(mode_str),
                workspace=state_manager.get("workspace"),
                max_iterations=state_manager.get("config").get("agent", {}).get("max_iterations", 50),
                temperature=state_manager.get("config").get("agent", {}).get("temperature", 0.1),
                max_tokens=state_manager.get("config").get("agent", {}).get("max_tokens", 4096),
                permission_callback=lambda tc: state_manager.get("permission_manager").check_and_approve(
                    tool_name=tc.name,
                    arguments=tc.arguments,
                ),
                system_prompt_extra=memory_context,
            )
            agent = AgentLoop(
                provider=engine,
                tools=tools,
                config=agent_cfg,
                usage_tracker=state_manager.get("usage_tracker"),
            )

            # Run the agent in a background thread to prevent blocking the async loop
            # and yield events back to the websocket client.
            def run_agent_loop(loop, ws, agent_prompt, prompt_mcp_clients):
                content_parts: list[str] = []
                try:
                    for event in agent.run(agent_prompt):
                        if event.type.value in {"content", "content_chunk"}:
                            content_parts.append(str(event.data or ""))
                        asyncio.run_coroutine_threadsafe(
                            send_agent_event(ws, event), loop
                        )
                    response_text = "".join(content_parts).strip()
                    session_manager = state_manager.get("session_manager")
                    if response_text and session_manager:
                        session_manager.save_message(
                            "assistant",
                            content=response_text,
                            type="assistant",
                        )
                except (RuntimeError, ValueError, OSError, LookupError) as ex:
                    logger.exception("Agent thread execution failure")
                    asyncio.run_coroutine_threadsafe(
                        ws.send_json({"type": "error", "content": f"Agent error: {ex}"}), loop
                    )
                finally:
                    for mcp_client in prompt_mcp_clients:
                        try:
                            mcp_client.close()
                        except (OSError, RuntimeError):
                            logger.debug("Failed to close web chat MCP client", exc_info=True)
                    with state_manager.get("web_agent_lock"):
                        state_manager.get("web_agent_threads").pop(session_id, None)

            loop = asyncio.get_running_loop()
            thread = threading.Thread(
                target=run_agent_loop,
                args=(loop, websocket, prompt, mcp_clients),
                name=f"nexus-web-agent-{session_id}",
                daemon=True,
            )
            with state_manager.get("web_agent_lock"):
                state_manager.get("web_agent_threads")[session_id] = thread

            def _log_thread_error(future):
                exc = future.exception()
                if exc:
                    logger.error(f"Agent thread failed: {exc}")

            future = asyncio.run_coroutine_threadsafe(
                asyncio.to_thread(thread.start), loop
            )
            future.add_done_callback(_log_thread_error)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for session: {session_id}")
    except (RuntimeError, json.JSONDecodeError, OSError):
        logger.exception("WebSocket endpoint error")


async def send_agent_event(ws: WebSocket, event: AgentEvent):
    """Helper to translate AgentEvent into WebSocket JSON messages."""
    try:
        match event.type:
            case "state_change":
                await ws.send_json({"type": "state_change", "data": event.data})
            case "thinking":
                await ws.send_json({"type": "thinking", "content": event.data})
            case "content":
                await ws.send_json({"type": "chunk", "content": event.data})
            case "content_chunk":
                await ws.send_json({"type": "chunk", "content": event.data})
            case "tool_call":
                await ws.send_json({
                    "type": "tool_call",
                    "name": event.data.get("name"),
                    "arguments": event.data.get("arguments"),
                })
            case "tool_result":
                await ws.send_json({
                    "type": "tool_result",
                    "name": event.data.get("name"),
                    "success": event.data.get("success"),
                    "output": event.data.get("output", "")[:2000],  # Truncate long logs
                })
            case "error":
                await ws.send_json({"type": "error", "content": str(event.data)})
            case "done":
                await ws.send_json({
                    "type": "done",
                    "iterations": event.data.get("iterations", 0),
                })
    except (RuntimeError, OSError) as e:
        logger.error(f"Failed to send websocket message: {e}")


def _welcome_html() -> str:
    return """
    <html>
        <head><title>NexusAgent API</title></head>
        <body>
            <h1>NexusAgent GUI Server is running!</h1>
            <p>Navigate to the GUI dashboard index page.</p>
        </body>
    </html>
    """


# --- SERVING WEB FRONTEND STATIC FILES ---

# We mount static directory last so API routes take precedence
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    @app.get("/")
    async def get_index():
        return HTMLResponse(content=_welcome_html())


def start_gui_server(
    model_path: str | None = None,
    provider: str | None = None,
    workspace: Path | None = None,
    config_path: str | None = None,
    data_dir: str | None = None,
    host: str | None = None,
    port: int | None = None,
    open_browser: bool = True,
):
    """Bootstrap and start the local FastAPI web server."""
    # Load configuration
    workspace_path = workspace or Path.cwd()
    state_manager.set("workspace", workspace_path)
    state_manager.set("config", load_config(
        config_path=config_path,
        workspace=workspace_path,
        data_dir=data_dir,
    ))

    # Initialize shared subsystems
    data_dir_path = state_manager.get("config").get("_data_dir", "~/.nexus-agent")
    state_manager.set("memory_manager", MemoryManager(data_dir=f"{data_dir_path}/memory"))
    state_manager.set("session_manager", SessionManager(data_dir=f"{data_dir_path}/sessions"))
    state_manager.set("permission_manager", PermissionManager())
    state_manager.get("permission_manager").load_from_config(state_manager.get("config"))
    state_manager.set("usage_tracker", UsageTracker(path=Path(os.path.expanduser(data_dir_path)) / "usage.json"))

    # Initialize RuntimeManager
    rm = RuntimeManager(state_manager.get("config"))
    state_manager.set("runtime_manager", rm)

    # Preload engine using ProviderFactory
    active_provider = provider or state_manager.get("config").get("providers", {}).get("active", "local")
    target_model = model_path
    if active_provider == "local" and not target_model:
        target_model = state_manager.get("config").get("local_model", {}).get("default_model", "")

    try:
        state_manager.set("engine", ProviderFactory.create_provider(active_provider, state_manager.get("config"), target_model))
    except (ImportError, ValueError, OSError, RuntimeError) as e:
        logger.warning(f"Failed to preload LLM provider '{active_provider}': {e}")


    # Set up host/port
    srv_config = state_manager.get("config").get("gui", {})
    bind_host = host or srv_config.get("host", "127.0.0.1")
    bind_port = port or srv_config.get("port", 7860)

    # Verify if port is available, find a free one if occupied
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((bind_host, bind_port))
        s.close()
    except OSError:
        old_port = bind_port
        bind_port = get_free_port()
        logger.warning(f"Port {old_port} occupied. Dynamic fallback to port {bind_port}.")

    url = f"http://{bind_host}:{bind_port}"
    logger.info(f"Starting {__app_name__} GUI server!")
    logger.info(f"Dashboard URL: {url}")
    logger.info(f"Workspace: {workspace_path}")

    # Automatically launch browser if requested
    if open_browser:
        def launch_browser():
            time.sleep(1.5)
            webbrowser.open(url)
        threading.Thread(target=launch_browser, daemon=True).start()

    # Run Uvicorn ASGI server
    uvicorn.run(app, host=bind_host, port=bind_port, log_level="warning")
