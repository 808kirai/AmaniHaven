import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

from .conftest import admin_token, counselor_token, reload_settings

phone = "+254733333333"
auth = {"Authorization": f"Bearer {counselor_token}"}


@pytest.fixture
def client(gateway):
    with TestClient(app) as c:
        yield c


def test_ussd_endpoint(client):
    r = client.post("/ussd", data={"sessionId": "s1", "phoneNumber": phone, "serviceCode": "*384*123#", "text": ""})
    assert r.status_code == 200
    assert r.text.startswith("CON AmaniHaven")


def test_ussd_followups_run_over_http(client, gateway):
    # the sms and the counselor alert behind a ussd screen must really go out, not only show as done
    form = {"sessionId": "s1", "phoneNumber": phone, "serviceCode": "*384*123#"}
    assert client.post("/ussd", data={**form, "text": "4*2"}).text.startswith("END")
    assert any(to == phone and "1199" in m for to, m in gateway.sent)
    client.post("/ussd", data={**form, "text": "4*1*1"})
    assert len(db.list_cases()) == 1
    assert any(to != phone for to, m in gateway.sent)


def test_webhook_secret_enforced(client, monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "s3cret")
    reload_settings()
    form = {"sessionId": "s1", "phoneNumber": phone, "text": ""}
    assert client.post("/ussd", data=form).status_code == 403
    assert client.post("/ussd?key=s3cret", data=form).status_code == 200


def test_inbound_sms_is_processed(client, gateway):
    r = client.post("/sms/inbound", data={"from": phone, "to": "22123", "text": "I want to die", "id": "1"})
    assert r.status_code == 200
    assert any(to == phone and "999" in m for to, m in gateway.sent)


def test_counselor_requires_token(client):
    assert client.get("/api/counselor/cases").status_code == 401
    assert client.get("/api/counselor/cases", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_counselor_workflow(client, gateway):
    client.post("/sms/inbound", data={"from": phone, "text": "I want to kill myself"})
    (case,) = client.get("/api/counselor/cases", headers=auth).json()
    assert case["tier"] == "crisis"
    assert case["thread"][0]["text"] == "I want to kill myself"
    assert phone not in case["phone_masked"]

    r = client.post(f"/api/counselor/cases/{case['id']}/reply", json={"text": "I'm here with you."}, headers=auth)
    assert r.status_code == 200 and r.json()["claimed_by"] == "amina"
    assert gateway.sent[-1] == (phone, "AmaniHaven counselor: I'm here with you.")

    # crisis cases can reveal the number under duty of care, and the reveal is audited
    assert client.post(f"/api/counselor/cases/{case['id']}/reveal-phone", headers=auth).json()["phone"] == phone

    assert client.post(f"/api/counselor/cases/{case['id']}/close", json={"note": "safety plan made"}, headers=auth).status_code == 200
    assert client.get("/api/counselor/cases", headers=auth).json() == []

    with db.tx() as c:
        actions = [r[0] for r in c.execute("select action from audit_log order by id")]
    assert actions == ["reply", "reveal_phone", "close"]


def test_reveal_phone_needs_consent_below_crisis(client):
    for _ in range(3):
        client.post("/sms/inbound", data={"from": phone, "text": "I feel hopeless"})
    (case,) = client.get("/api/counselor/cases", headers=auth).json()
    assert client.post(f"/api/counselor/cases/{case['id']}/reveal-phone", headers=auth).status_code == 403


def test_reply_blocked_after_stop(client):
    client.post("/sms/inbound", data={"from": phone, "text": "CALL"})
    client.post("/sms/inbound", data={"from": phone, "text": "STOP"})
    (case,) = client.get("/api/counselor/cases", headers=auth).json()
    r = client.post(f"/api/counselor/cases/{case['id']}/reply", json={"text": "hello"}, headers=auth)
    assert r.status_code == 409


def test_admin_stats(client):
    client.post("/sms/inbound", data={"from": phone, "text": "I want to kill myself"})
    assert client.get("/api/admin/stats").status_code == 401
    stats = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert stats["open_cases"] == {"crisis": 1}
    assert phone not in str(stats)


def test_dashboard_served(client):
    r = client.get("/counselor")
    assert r.status_code == 200 and "AmaniHaven" in r.text
