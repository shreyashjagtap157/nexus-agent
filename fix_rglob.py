with open("src/nexus_agent/cli/commands/session_mixin.py") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "files = [str(f) for f in self.workspace.rglob(\"*.py\")][:20]" in line:
        print(f"Found line at {i}: {line.strip()}")
        break
