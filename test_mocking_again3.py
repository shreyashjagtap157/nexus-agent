import sys

def check_openvino():
    runtimes = []
    try:
        import openvino
        runtimes.append(1)
    except ImportError:
        pass
    except Exception as e:
        print("EXCEPTION:", type(e))
    return runtimes

def test():
    # Make sure 'openvino' exists in sys.modules, like the CI when `openvino` package is installed globally
    try:
        import openvino
    except ImportError:
        print("openvino not installed")

    from unittest.mock import patch
    # Don't mock openvino.telemetry
    with patch.dict('sys.modules', {'openvino': None}, clear=False):
        print("Running check:")
        print(check_openvino())

test()
