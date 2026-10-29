from app.core.config import settings

API = "/api/v1"
EVIL = "https://evil.example.com"


def preflight(client, origin):
    return client.options(
        f"{API}/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


def test_preflight_from_the_frontend_origin_is_allowed(client):
    response = preflight(client, settings.FRONTEND_HOST)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == settings.FRONTEND_HOST


def test_preflight_from_any_other_origin_is_rejected(client):
    response = preflight(client, EVIL)

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_responses_are_not_readable_from_other_origins(client):
    response = client.get("/health", headers={"Origin": EVIL})

    assert "access-control-allow-origin" not in response.headers


def test_cors_does_not_enable_credentialed_requests(client):
    # A API autentica por header Authorization, não por cookie.
    response = client.get("/health", headers={"Origin": settings.FRONTEND_HOST})

    assert response.headers["access-control-allow-origin"] == settings.FRONTEND_HOST
    assert "access-control-allow-credentials" not in response.headers


def test_only_the_methods_and_headers_the_frontend_uses_are_allowed(client):
    response = preflight(client, settings.FRONTEND_HOST)

    allowed_methods = set(response.headers["access-control-allow-methods"].split(", "))
    assert allowed_methods == {"GET", "POST", "PATCH", "DELETE"}
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers and "content-type" in allowed_headers
    assert "*" not in allowed_headers
