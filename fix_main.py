import sys

filepath = "src/nexus_agent/__main__.py"
with open(filepath, "r") as f:
    content = f.read()

# Add import itertools
content = content.replace("import sys\n", "import sys\nimport itertools\n")

# Replace greedy rglob
content = content.replace(
    '[str(f) for f in Path.cwd().rglob("*.py")][:20]',
    'list(itertools.islice((str(f) for f in Path.cwd().rglob("*.py")), 20))'
)

with open(filepath, "w") as f:
    f.write(content)
