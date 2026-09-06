"""
Unit and integration tests for reverse-proxy deployment topology and trusted forwarded headers (ADV-SEC-002).

Tests:
1. Direct connection (development topology without ProxyHeadersMiddleware):
   - Spoofed X-Forwarded-For is ignored by FastAPI request.client.host.
   - Attacker cannot bypass registration/login rate limits by forging X-Forwarded-For.
2. Untrusted peer with ProxyHeadersMiddleware enabled:
   - Client connecting from an untrusted peer IP has X-Forwarded-For rejected.
   - Rate limiting binds to the untrusted peer IP, blocking spoofing attacks.
3. Trusted proxy with ProxyHeadersMiddleware enabled:
   - Trusted proxy (e.g. 10.0.0.1) forwarding valid client IPs has X-Forwarded-For honored.
   - Client A exhausting rate limits does not exhaust Client B or lock out the shared proxy IP.
4. Architectural invariant:
   - Route handlers in auth.py do not parse raw X-Forwarded-For headers directly from request.headers.
"""
import ast
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.auth.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import app


@pytest.fixture
def override_db(db_session: Session):
    """Override get_db dependency to use the isolated test database session."""
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


def test_direct_connection_ignores_spoofed_forwarded_headers(override_db, db_session: Session):
    """
    In direct/development topology (no ProxyHeadersMiddleware),
    FastAPI request.client.host reflects the socket peer IP regardless of X-Forwarded-For.
    Attacker sending rotating spoofed X-Forwarded-For headers is still constrained by peer IP.
    """
    rate_limiter.clear()
    attacker_peer_ip = "198.51.100.5"
    client = TestClient(app, client=(attacker_peer_ip, 54321))

    # Perform 5 registration attempts with rotating fake XFF headers
    for i in range(5):
        res = client.post(
            "/api/auth/register",
            json={
                "email": f"attacker_{i}@example.com",
                "username": f"attacker_{i}",
                "password": "Password123!",
            },
            headers={"X-Forwarded-For": f"203.0.113.{i+1}"},
        )
        assert res.status_code == 201, f"Attempt {i+1} should succeed"

    # 6th attempt with another spoofed IP must be RATE_LIMITED because peer IP is exhausted
    res_blocked = client.post(
        "/api/auth/register",
        json={
            "email": "attacker_blocked@example.com",
            "username": "attacker_blocked",
            "password": "Password123!",
        },
        headers={"X-Forwarded-For": "203.0.113.99"},
    )
    assert res_blocked.status_code == 429
    assert res_blocked.json()["error"]["code"] == "RATE_LIMITED"


def test_untrusted_peer_spoofed_forwarded_headers_rejected_by_proxy_middleware(override_db):
    """
    When ProxyHeadersMiddleware is configured with trusted_hosts=['10.0.0.1'],
    an incoming connection from an untrusted peer ('198.51.100.5') has its
    X-Forwarded-For header rejected. The rate limiter binds to '198.51.100.5'.
    """
    rate_limiter.clear()
    trusted_proxy_ip = "10.0.0.1"
    untrusted_attacker_ip = "198.51.100.5"

    proxy_app = ProxyHeadersMiddleware(app, trusted_hosts=[trusted_proxy_ip])
    client = TestClient(proxy_app, client=(untrusted_attacker_ip, 54321))

    # Attacker tries to spoof client IP on 5 registration requests
    for i in range(5):
        res = client.post(
            "/api/auth/register",
            json={
                "email": f"untrusted_{i}@example.com",
                "username": f"untrusted_{i}",
                "password": "Password123!",
            },
            headers={"X-Forwarded-For": f"192.0.2.{i+1}"},
        )
        assert res.status_code == 201

    # 6th attempt must fail with 429 RATE_LIMITED
    res_blocked = client.post(
        "/api/auth/register",
        json={
            "email": "untrusted_fail@example.com",
            "username": "untrusted_fail",
            "password": "Password123!",
        },
        headers={"X-Forwarded-For": "192.0.2.100"},
    )
    assert res_blocked.status_code == 429
    assert res_blocked.json()["error"]["code"] == "RATE_LIMITED"


def test_trusted_proxy_honors_forwarded_for_and_prevents_shared_ip_exhaustion(override_db):
    """
    When requests arrive through a trusted reverse proxy ('10.0.0.1'),
    ProxyHeadersMiddleware unpacks X-Forwarded-For so distinct clients
    are tracked in separate rate limit buckets rather than exhausting the proxy IP.
    """
    rate_limiter.clear()
    trusted_proxy_ip = "10.0.0.1"
    client_a_ip = "203.0.113.10"
    client_b_ip = "203.0.113.20"

    proxy_app = ProxyHeadersMiddleware(app, trusted_hosts=[trusted_proxy_ip])
    client = TestClient(proxy_app, client=(trusted_proxy_ip, 54321))

    # Client A makes 5 registrations via proxy
    for i in range(5):
        res_a = client.post(
            "/api/auth/register",
            json={
                "email": f"client_a_{i}@example.com",
                "username": f"client_a_{i}",
                "password": "Password123!",
            },
            headers={"X-Forwarded-For": client_a_ip},
        )
        assert res_a.status_code == 201

    # Client A's 6th registration is rejected
    res_a_blocked = client.post(
        "/api/auth/register",
        json={
            "email": "client_a_blocked@example.com",
            "username": "client_a_blocked",
            "password": "Password123!",
        },
        headers={"X-Forwarded-For": client_a_ip},
    )
    assert res_a_blocked.status_code == 429
    assert res_a_blocked.json()["error"]["code"] == "RATE_LIMITED"

    # Client B making a request through the SAME proxy succeeds (not locked out by Client A)
    res_b = client.post(
        "/api/auth/register",
        json={
            "email": "client_b_valid@example.com",
            "username": "client_b_valid",
            "password": "Password123!",
        },
        headers={"X-Forwarded-For": client_b_ip},
    )
    assert res_b.status_code == 201
    assert res_b.json()["user"]["username"] == "client_b_valid"


def test_auth_endpoints_do_not_parse_raw_forwarded_headers():
    """
    Verify architectural invariant:
    Route handlers must rely exclusively on request.client.host and must not
    parse X-Forwarded-For or Client-IP from request.headers directly.
    """
    import inspect
    from app.api import auth

    source = inspect.getsource(auth)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value.lower()
            assert "x-forwarded-for" not in val, (
                "auth.py must not reference 'x-forwarded-for' directly. "
                "Client IP resolution must remain delegated to ASGI proxy headers middleware."
            )
            assert "x-real-ip" not in val, (
                "auth.py must not reference 'x-real-ip' directly. "
                "Client IP resolution must remain delegated to ASGI proxy headers middleware."
            )
