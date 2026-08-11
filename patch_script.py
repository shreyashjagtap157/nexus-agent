import subprocess
with open("src/nexus_agent/cli/commands/agent_mixin.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "f\"{' ' * PAD}{'\\u2500' * left_w}\\u252c{'\\u2500' * right_w}\"" in line:
        print(f"Found bug at {i}: {line}")
