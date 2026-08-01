import sys
content = open('src/nexus_agent/cli/commands/agent_mixin.py').read()
content = content.replace("f\"{' ' * PAD}{'\\u2500' * left_w}\\u252c{'\\u2500' * right_w}\"", "(' ' * PAD) + ('\\u2500' * left_w) + '\\u252c' + ('\\u2500' * right_w)")
open('src/nexus_agent/cli/commands/agent_mixin.py', 'w').write(content)
