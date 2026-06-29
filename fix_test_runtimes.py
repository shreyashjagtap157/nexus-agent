with open("tests/nexus_agent/cli/test_runtimes.py", "r") as f:
    content = f.read()

content = content.replace('with patch.dict("sys.modules", {"jax": None}):\n            runtimes = _check_openvino()', 'with patch.dict("sys.modules", {"openvino": None}):\n            runtimes = _check_openvino()')

with open("tests/nexus_agent/cli/test_runtimes.py", "w") as f:
    f.write(content)
