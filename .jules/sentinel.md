## 2025-02-27 - [High] Cross-Site WebSocket Hijacking (CSWSH)
**Vulnerability:** FastAPIs websocket endpoint `websocket_endpoint` inside `src/nexus_agent/gui/server.py` lacked `Origin` header validation against the `Host` header. Without this check, the application was susceptible to CSWSH attacks.

**Learning:** When adding or modifying WebSocket endpoints in FastAPI or other web frameworks, it is important to explicitly validate the `Origin` header. An attacker could otherwise exploit an authenticated user by coercing their browser into establishing a WebSocket connection to a vulnerable endpoint. When evaluating origin vs host, care should be taken to allow expected local development patterns to prevent regressions (e.g., origin `localhost:3000` calling host `127.0.0.1:7860`).

**Prevention:** Explicitly handle and reject connections where `origin == "null"`. Ensure the hostname of the incoming `Origin` matches the `Host` header, or is explicitly in an allowlist of valid CORS/local domains (`127.0.0.1`, `localhost`).
