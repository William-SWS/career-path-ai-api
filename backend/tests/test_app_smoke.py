import pytest

API = "/api/v1"


def test_healthcheck_responds_online(client):
    response = client.get(f"{API}/check/")

    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_unknown_route_returns_error_envelope(client):
    response = client.get(f"{API}/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"status": 404, "code": "http_error", "message": "Not Found"}
    }


def test_invalid_body_returns_validation_error_envelope(client):
    response = client.post(f"{API}/auth/login", json={})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "status": 422,
            "code": "request_validation_error",
            "message": "Request validation error",
        }
    }


EXPECTED_ROUTES = {
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("POST", "/auth/login-form"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
    ("POST", "/auth/forgot-password"),
    ("POST", "/auth/reset-password"),
    ("GET", "/users/me"),
    ("POST", "/resume-analysis/"),
    ("POST", "/interview-guide/"),
    ("POST", "/development-trail/"),
}


def test_public_routes_are_mounted_under_single_api_prefix(client):
    schema = client.get("/openapi.json").json()
    mounted = {
        (method.upper(), path)
        for path, operations in schema["paths"].items()
        for method in operations
    }

    expected = {(method, f"{API}{path}") for method, path in EXPECTED_ROUTES}
    assert expected <= mounted
    assert not any(path.startswith(f"{API}{API}") for _, path in mounted)


@pytest.mark.parametrize(
    "path",
    ["/resume-analysis/", "/interview-guide/", "/development-trail/", "/users/me"],
)
def test_protected_routes_reject_missing_token(client, path):
    response = client.get(f"{API}{path}")

    assert response.status_code == 401
