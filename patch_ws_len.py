import re

with open("tests/test_websocket_cswsh.py", "r") as f:
    content = f.read()

content = content.replace("    # It should connect successfully (will eventually timeout waiting for json, which is fine, or we can send empty)\n", "    # It should connect successfully\n")

with open("tests/test_websocket_cswsh.py", "w") as f:
    f.write(content)
