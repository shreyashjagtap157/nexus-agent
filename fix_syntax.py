with open("src/nexus_agent/cli/commands/agent_mixin.py", "r") as f:
    content = f.read()

content = content.replace(r"f\"{' ' * PAD}{'\u2500' * left_w}\u252c{'\u2500' * right_w}\",", "f\"{' ' * PAD}{chr(0x2500) * left_w}{chr(0x252c)}{chr(0x2500) * right_w}\",")

with open("src/nexus_agent/cli/commands/agent_mixin.py", "w") as f:
    f.write(content)
