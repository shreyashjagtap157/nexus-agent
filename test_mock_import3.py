import importlib

def _check_openvino():
    runtimes = []
    try:
        import openvino
        runtimes.append(openvino)
    except ImportError as e:
        print(f"Caught {type(e)}")
        pass
    return runtimes

def test_mocking():
    print("Test running")
    import sys
    from unittest.mock import patch

    # We patch the dict with None
    # Wait, in the actual test, it's:
    # with patch.dict("sys.modules", {"openvino": None}):
    # Let's create a fake openvino package in a temp dir
    pass
