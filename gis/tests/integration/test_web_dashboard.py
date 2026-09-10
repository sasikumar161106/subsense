import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_web_dashboard_html_served():
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "SubSense" in response.text
    assert "DGMS" in response.text
    assert "map-canvas" in response.text

def test_web_dashboard_css_served():
    response = client.get("/dashboard/styles/dashboard.css")
    assert response.status_code == 200
    assert "--color-critical" in response.text

def test_web_dashboard_js_served():
    response = client.get("/dashboard/src/app.js")
    assert response.status_code == 200
    assert "SUBSENSE-TDD-GIS-005" in response.text
