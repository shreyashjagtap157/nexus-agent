from fastapi import HTTPException


from nexus_agent.gui.server import _require_local_client


def test_gui_mutation_access_rejects_remote_clients():
    request = type("Request", (), {"client": type("Client", (), {"host": "203.0.113.10"})()})()
    try:
        _require_local_client(request)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Remote GUI mutation request was accepted")


def test_gui_mutation_access_accepts_loopback_clients():
    for host in ("127.0.0.1", "::1", "localhost"):
        request = type("Request", (), {"client": type("Client", (), {"host": host})()})()
        _require_local_client(request)
