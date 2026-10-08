import re

files_to_fix = [
    "src/nexus_agent/cli/commands/agent_mixin.py",
    "src/nexus_agent/tools/memory.py",
    "src/nexus_agent/core/orchestrator.py",
    "src/nexus_agent/cli/command_dispatcher.py",
    "src/nexus_agent/backend.py",
    "src/nexus_agent/gui/server.py",
    "src/nexus_agent/cli/session_handler.py",
    "src/nexus_agent/cli/doctor.py",
    "src/nexus_agent/cli/app.py",
    "src/nexus_agent/__main__.py",
    "src/nexus_agent/tools/code_intel.py",
    "src/nexus_agent/tools/council.py",
    "src/nexus_agent/tools/file_ops.py",
    "src/nexus_agent/tools/git_ops.py",
    "src/nexus_agent/tools/lsp_client.py",
    "src/nexus_agent/tools/lsp_transport.py",
    "src/nexus_agent/tools/rag_search.py",
    "src/nexus_agent/tools/shell.py",
    "src/nexus_agent/tools/todowrite.py",
    "src/nexus_agent/tools/webfetch.py",
    "src/nexus_agent/training/data/watchdog.py",
    "src/nexus_agent/training/model/rdt.py"
]

# Note: memory says:
# "When fixing linting/typing issues (e.g., from local runs like 'ruff check' or CI failures), adhere to the 'avoid scope creep rule': limit your fixes strictly to errors directly introduced by your code changes. Explicitly ignore pre-existing global violations in untouched files or unmodified lines, complete the required pre-commit steps, and submit the branch as-is."

# Let's check which files I changed in my commit.
