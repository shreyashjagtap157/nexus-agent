def _check_openvino():
    runtimes = []
    try:
        import openvino
        runtimes.append(openvino)
    except ImportError:
        pass
    return runtimes

def test_mocking():
    print("Test running")
    import sys
    from unittest.mock import patch

    class MockOpenVino:
        __file__ = '/mock/openvino.py'

    # Simulate openvino is installed and previously loaded
    sys.modules['openvino'] = MockOpenVino()

    # We patch the dict with None
    with patch.dict('sys.modules', {'openvino': None}):
        print(_check_openvino())

test_mocking()
