import subprocess

files_to_fix = [
    "src/nexus_agent/cli/commands/_base.py",
    "src/nexus_agent/cli/commands/agent_mixin.py",
    "src/nexus_agent/tools/code_intel.py",
    "src/nexus_agent/tools/council.py",
    "src/nexus_agent/tools/file_ops.py",
    "src/nexus_agent/tools/git_ops.py",
    "src/nexus_agent/tools/lsp_client.py",
    "src/nexus_agent/tools/lsp_transport.py",
    "src/nexus_agent/tools/memory.py",
    "src/nexus_agent/tools/rag_search.py",
    "src/nexus_agent/tools/shell.py",
    "src/nexus_agent/tools/todowrite.py",
    "src/nexus_agent/tools/webfetch.py",
    "src/nexus_agent/training/data/watchdog.py",
    "src/nexus_agent/training/model/rdt.py"
]

subprocess.run(["ruff", "format"] + files_to_fix)
