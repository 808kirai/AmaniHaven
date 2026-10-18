from app import db
from app.privacy import hash_phone
from app.ussd import handle_ussd

from .conftest import alert_number, run

phone = "+254711111111"


def press(path):
    # sends a keypress path and runs any followups the way the web app would
    result = handle_ussd(phone, path)
    for f in result.followups:
        run(f())
    return result


def test_main_menu():
    r = press("")
    assert r.body.startswith("CON ")
    assert "Urgent help" in r.text


def test_breathing_exercise_runs_to_end():
    assert "Breathe IN" in press("2*1").text
    r = press("2*1*1*1*1*1")
    assert r.end and "Well done" in r.text


def test_back_and_home():
    assert "Urgent help" in press("2*0").text
    assert "Urgent help" in press("2*1*1*00").text


def test_invalid_choice_keeps_place():
    r = press("2*9")
    assert r.text.startswith("Invalid choice.") and "Choose an exercise" in r.text
    assert "Breathe IN" in press("2*9*1").text


def test_checkin_scores_once(gateway):
    r = press("3*1*4*4*4*4*2")
    assert "very hard" in r.text
    # moving on to a calm exercise must not save the check in again
    press("3*1*4*4*4*4*2*1")
    with db.tx() as c:
        rows = c.execute("select phq4, safety_yes from checkins").fetchall()
    assert [tuple(r) for r in rows] == [(12, 0)]


def test_checkin_low_score():
    assert "coping well" in press("3*1*1*1*1*1*2").text


def test_checkin_safety_yes_offers_help_without_contacting(gateway):
    r = press("3*1*2*2*2*2*1")
    assert "999" in r.text and "counselor calls me" in r.text
    # nothing is sent unless they ask
    assert gateway.sent == []
    assert db.list_cases() == []


def test_urgent_callback_creates_case_and_alerts(gateway):
    r = press("4*1*1")
    assert r.end
    cases = db.list_cases()
    assert len(cases) == 1 and cases[0]["tier"] == "crisis"
    assert db.get_user(hash_phone(phone))["callback_consent"] == 1
    alerts = [m for to, m in gateway.sent if to == alert_number]
    assert alerts and phone not in alerts[0]


def test_callback_decline_returns_home(gateway):
    assert "Urgent help" in press("4*1*2").text
    assert db.list_cases() == []


def test_urgent_sms(gateway):
    r = press("4*2")
    assert r.end
    assert gateway.sent and "1199" in gateway.sent[0][1]


def test_language_switch_persists():
    r = press("5*2")
    assert "Lugha imehifadhiwa" in r.text and "Msaada wa dharura" in r.text
    assert "Msaada wa dharura" in press("").text


def test_talk_by_sms_sends_welcome(gateway):
    r = press("1")
    assert r.end
    assert gateway.sent[0][0] == phone and "Welcome to AmaniHaven" in gateway.sent[0][1]


def test_delete_my_data():
    press("4")
    r = press("6*1*1")
    assert r.end and "deleted" in r.text
    assert db.get_user(hash_phone(phone)) is None
