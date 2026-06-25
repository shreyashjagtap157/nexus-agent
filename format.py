import subprocess
subprocess.run(["ruff", "check", "--fix", "--unsafe-fixes", "src/nexus_agent/__main__.py", "src/nexus_agent/cli/commands/interactive_ui.py", "src/nexus_agent/cli/commands/session_mixin.py", "src/nexus_agent/utils/fs.py", "src/nexus_agent/core/project_context.py"])
