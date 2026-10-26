import pytest
from fastapi.testclient import TestClient

from app import demo
from app.config import get_settings
from app.main import app

from .conftest import alert_number, reload_settings


@pytest.fixture
def client(gateway, monkeypatch):
    monkeypatch.setenv("DEMO_ENABLED", "true")
    reload_settings()
    demo.store.__init__()
    with TestClient(app) as c:
        yield c


def start(client):
    r = client.post("/api/demo/start")
    assert r.status_code == 200
    return r.json()["id"]


def test_demo_is_off_by_default(gateway):
    with TestClient(app) as c:
        assert c.get("/demo").status_code == 404
        assert c.post("/api/demo/start").status_code == 404


def test_demo_page_served(client):
    r = client.get("/demo")
    assert r.status_code == 200 and "AmaniHaven" in r.text


def test_crisis_text_opens_case_and_pages_without_sending_to_a_real_phone(client, gateway):
    sid = start(client)
    state = client.post("/api/demo/sms", json={"id": sid, "text": "I want to end my life"}).json()
    replies = [m["text"] for m in state["messages"] if m["direction"] == "out"]
    assert replies and "999" in replies[0]
    assert state["case"]["tier"] == "crisis" and state["case"]["paged"]
    # the only real sms is the alert to the on call counselor, the demo phone's reply stays on the page
    assert gateway.sent and all(to == alert_number for to, _ in gateway.sent)


def test_counselor_reply_lands_on_the_demo_phone(client):
    sid = start(client)
    client.post("/api/demo/sms", json={"id": sid, "text": "I want to end my life"})
    state = client.post("/api/demo/reply", json={"id": sid, "text": "I'm here, can we talk?"}).json()
    assert "I'm here, can we talk?" in state["messages"][-1]["text"]
    assert state["case"]["claimed_by"] == demo.demo_counselor


def test_reply_needs_an_open_case(client):
    sid = start(client)
    assert client.post("/api/demo/reply", json={"id": sid, "text": "hello"}).status_code == 409


def test_ussd_menu_and_its_sms(client):
    sid = start(client)
    first = client.post("/api/demo/ussd", json={"id": sid, "text": ""}).json()
    assert not first["end"] and "AmaniHaven" in first["text"]
    end = client.post("/api/demo/ussd", json={"id": sid, "text": "4*2"}).json()
    assert end["end"]
    state = client.get(f"/api/demo/state?id={sid}").json()
    assert any("1199" in m["text"] for m in state["messages"])


def test_unknown_session(client):
    assert client.post("/api/demo/sms", json={"id": "nope", "text": "hi"}).status_code == 404
    assert client.get("/api/demo/state?id=nope").status_code == 404


def test_oldest_session_is_dropped(client, monkeypatch):
    monkeypatch.setattr(demo, "max_sessions", 2)
    first = start(client)
    start(client)
    start(client)
    assert client.get(f"/api/demo/state?id={first}").status_code == 404


def test_demo_refused_outside_the_sandbox(monkeypatch):
    for name, value in {"APP_ENV": "production", "DEMO_ENABLED": "true", "AT_USERNAME": "amanihaven", "AT_API_KEY": "k",
                        "WEBHOOK_SECRET": "w", "SMS_GATEWAY": "africastalking"}.items():
        monkeypatch.setenv(name, value)
    reload_settings()
    with pytest.raises(RuntimeError, match="sandbox"):
        get_settings()
