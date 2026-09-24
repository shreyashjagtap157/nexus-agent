import sys
import json
import subprocess

def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.stdout.strip()

msg = run("git log -1 --pretty=%B")

new_msg = msg + """

In addition, fixed another CI failure in `tests/nexus_agent/cli/test_wizard.py` by applying the `ModelManager.detect_hardware` mock to the setup function. This ensures that the command line tests don't timeout running real hardware detection via `subprocess` on GitHub Action Runners."""

with open("msg.txt", "w") as f:
    f.write(new_msg)
