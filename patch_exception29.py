import re

with open('src/nexus_agent/gui/server.py', 'r') as f:
    content = f.read()

# Using `raise WebSocketException` inside `websocket_endpoint` works.
# The only issue is `test_server_ws.py` needs to properly catch it.
# Let's fix `test_server_ws.py` to use a native fastAPI client behavior.
# Actually, if I raise WebSocketException before the `while True:` loop starts, `TestClient` handles it correctly.
# My previous `patch_exception28.py` used `with client.websocket_connect` and `try...except`.
# But `client.websocket_connect` actually raises `WebSocketDisconnect` inside its `__enter__` if the server closes the connection during setup.
# So `with pytest.raises(WebSocketDisconnect)` around `with client.websocket_connect:` is correct!
# But wait, why did it fail in `patch_exception28.py`?
# Ah! I know! In `patch_exception28.py`, `test_server_ws.py` has:
# `    # Origin mismatch\n`
# `    with client.websocket_connect("/api/ws/test", headers={"Origin": "http://attacker.com"}) as ws:\n`
# `        try:\n`
# `            ws.receive_json()\n`
# `            assert False, "Should have disconnected"\n`
# `        except Exception as e:\n`
# `            assert hasattr(e, "code")\n`
# `            assert e.code == 1008`
#
# But `with client.websocket_connect()` itself raised the exception! So it never reached `ws.receive_json()`!
# That's why it didn't hit my `try...except` and just threw the exception upwards!
# BUT when I had `with pytest.raises(WebSocketDisconnect):` AROUND `with client.websocket_connect:`, it said `FAILED: DID NOT RAISE`!
# Let me look at my exact test output:
# `>       with pytest.raises(WebSocketDisconnect) as exc_info:`
# `E       Failed: DID NOT RAISE WebSocketDisconnect`
# If it did not raise, it means `client.websocket_connect` succeeded!
# WHY did `client.websocket_connect` succeed if it raised `WebSocketException`?
# BECAUSE when it succeeded, I was using `await websocket.close()` inside `server.py`!
# When I used `raise WebSocketException` in `server.py`, the test passed! Wait! Did it?
# In `patch_exception21.py`, I put `raise WebSocketException` back into `server.py`.
# AND THEN I ran tests and it gave `FAILED: DID NOT RAISE WebSocketDisconnect`.
# THIS MAKES NO SENSE! If `raise WebSocketException` is there, why does it not raise?
# Let's look at `server.py`:
