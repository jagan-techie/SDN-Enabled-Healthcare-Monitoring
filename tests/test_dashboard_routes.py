# tests/test_dashboard_routes.py - Unit tests for Flask web dashboard, auth, CSRF, and REST API
import sys
import re
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dashboard.app import app
from db.session import init_db
from db.seed import seed_database

@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True
    init_db()
    seed_database()
    with app.test_client() as client:
        yield client

def get_csrf_token_from_html(html_text: str) -> str:
    match = re.search(r'name="csrf-token"\s+content="([^"]+)"', html_text)
    if not match:
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html_text)
    return match.group(1) if match else ""

def test_unauthenticated_redirect_to_login(client):
    res = client.get("/live", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]

def test_login_flow_and_session(client):
    # 1. Fetch login page to get CSRF token
    res_get = client.get("/login")
    assert res_get.status_code == 200
    token = get_csrf_token_from_html(res_get.text)
    assert len(token) > 0

    # 2. Test invalid password
    res_bad = client.post("/login", data={
        "username": "admin",
        "password": "wrongpassword",
        "csrf_token": token
    })
    assert b"Invalid username or password" in res_bad.data

    # 3. Test valid login
    res_ok = client.post("/login", data={
        "username": "admin",
        "password": "admin123",
        "csrf_token": token
    }, follow_redirects=True)
    assert res_ok.status_code == 200
    assert b"CardioSDN Guard" in res_ok.data

def test_authenticated_pages_and_disclaimer(client):
    pages = ["/live", "/alerts", "/history", "/network"]
    for page in pages:
        res = client.get(page)
        assert res.status_code == 200
        # Mandatory disclaimer check
        assert b"Not a Certified Medical Device" in res.data or b"Not a medical device" in res.data

    # Admin route redirects to live monitor
    res_admin = client.get("/admin", follow_redirects=False)
    assert res_admin.status_code == 302
    assert "/live" in res_admin.headers["Location"]

def test_rest_api_patients_and_live_telemetry(client):
    res = client.get("/api/patients")
    assert res.status_code == 200
    patients = res.json
    assert len(patients) >= 3

    # Test live endpoint for P101
    res_live = client.get("/api/patients/P101/live")
    assert res_live.status_code == 200
    data = res_live.json
    assert "hr" in data
    assert "spo2" in data
    assert "temp" in data
    assert "overall_status" in data
    assert len(data["ecg_batch"]) == 360

def test_rest_api_alerts_and_acknowledgment(client):
    res = client.get("/api/alerts")
    assert res.status_code == 200
    alerts = res.json
    assert isinstance(alerts, list)

    # Fetch fresh CSRF token
    res_page = client.get("/alerts")
    token = get_csrf_token_from_html(res_page.text)

    # Acknowledge alert without CSRF should fail with 403
    res_no_csrf = client.post("/api/alerts/1/ack")
    assert res_no_csrf.status_code == 403

    # Acknowledge alert with CSRF
    res_ack = client.post("/api/alerts/1/ack", headers={"X-CSRFToken": token})
    # If alert #1 exists, status is 200, else 404 (validates route logic)
    assert res_ack.status_code in (200, 404)

def test_rest_api_network_metrics(client):
    res = client.get("/api/network/metrics")
    assert res.status_code == 200
    data = res.json
    assert "off" in data
    assert "on" in data
    # Priority ON latency should be significantly lower than Priority OFF
    assert data["on"]["latency"] < data["off"]["latency"]
    assert data["on"]["loss"] <= data["off"]["loss"]
