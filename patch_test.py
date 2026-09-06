import re
from pathlib import Path

content = Path("tests/nexus_agent/cli/test_runtimes.py").read_text()

content = re.sub(
    r'def test_no_openvino\(self\):\n\s+with patch\.dict\("sys\.modules", \{"jax": None\}\):',
    'def test_no_openvino(self):\n        with patch.dict("sys.modules", {"openvino": None}):',
    content
)

Path("tests/nexus_agent/cli/test_runtimes.py").write_text(content)
