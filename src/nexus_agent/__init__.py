"""
NexusAgent — Offline-First LLM Coding Agent
============================================

A local-first multi-agent development and research workbench that loads and runs LLM models
locally on the user's machine by default, with optional cloud provider connections.

Features:
- Local GGUF model hosting via llama-cpp-python
- Rich terminal TUI (Textual) and web-based GUI (FastAPI)
- Persistent memory system (working, long-term, episodic)
- Multi-agent orchestration with dynamic peer teams, shared blackboard messaging and specialized roles
- 9+ cloud provider connectors
- MCP protocol support
- Modular skill system
- Permission-based tool execution with sandboxing
- Web, CLI/TUI and native Rust client surfaces
"""

__version__ = "0.2.0"
__app_name__ = "NexusAgent"

__all__ = [
    "__version__",
    "__app_name__",
]
