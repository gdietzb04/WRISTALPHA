from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from wristalpha import __version__
from wristalpha.api import app


def test_health_reports_version() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
    assert any(isinstance(route, APIRoute) and route.path == "/health" for route in app.routes)
