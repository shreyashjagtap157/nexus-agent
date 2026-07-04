import subprocess

def run_command(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running {cmd}:\n{result.stderr}")
    return result.stdout

print(run_command("python -m ruff check src/"))
