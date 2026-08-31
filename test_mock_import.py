import builtins

original_import = builtins.__import__

def _check_openvino():
    runtimes = []
    try:
        import openvino
        runtimes.append(1)
    except ImportError:
        pass
    return runtimes

def test_mocking():
    print("Test running")
    import sys
    from unittest.mock import patch

    # Simulate openvino is installed
    sys.modules['openvino'] = type('MockModule', (), {'__file__': '/mock/openvino.py'})()

    with patch.dict('sys.modules', {'openvino': None}):
        print(_check_openvino())

test_mocking()
