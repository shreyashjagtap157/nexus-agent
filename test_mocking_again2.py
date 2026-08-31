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
    # What if openvino.telemetry or something else is loaded?
    import openvino
    import openvino_telemetry

    from unittest.mock import patch
    with patch.dict('sys.modules', {'openvino': None}):
        print("Running check:")
        print(check_openvino())

test()
