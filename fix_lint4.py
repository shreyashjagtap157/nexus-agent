import sys

main_file = "src/nexus_agent/cli/commands/agent_mixin.py"
with open(main_file, "r") as f:
    content = f.read()

lines = content.split("\n")
for i, line in enumerate(lines):
    if "f\"{' ' * PAD}\" + \"─\" * left_w + \"┬\" + \"─\" * right_w" in line:
        lines[i] = "            \" \" * PAD + \"\u2500\" * left_w + \"\u252c\" + \"\u2500\" * right_w,"
    elif "f\"{' ' * PAD}\" + \"─\" * total_w" in line:
        lines[i] = "            \" \" * PAD + \"\u2500\" * total_w,"
    elif "\"─\" * header_w" in line:
        lines[i] = "            \"\u2500\" * header_w,"

with open(main_file, "w") as f:
    f.write("\n".join(lines))
