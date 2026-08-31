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
    import openvino

    from unittest.mock import patch
    with patch.dict('sys.modules', {'openvino': None}):
        print("Running check:")
        print(check_openvino())

test()
