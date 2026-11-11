from app import db
from app.privacy import hash_phone
from app.sms import handle_inbound_sms

from .conftest import alert_number, reload_settings, run

phone = "+254722222222"


def uh():
    # worked out per test because the pepper is set by the fixture
    return hash_phone(phone)


def text(msg):
    run(handle_inbound_sms(phone, msg))


def replies(gateway):
    return [m for to, m in gateway.sent if to == phone]


def alerts(gateway):
    return [m for to, m in gateway.sent if to == alert_number]


def test_routine_message_gets_a_tip(gateway):
    text("I'm stressed about my exams")
    (reply,) = replies(gateway)
    assert reply.startswith("Thank you for sharing.")
    # the tip matches the topic
    assert "Stress shrinks" in reply
    assert db.list_cases() == []


def test_messages_are_encrypted_at_rest(gateway):
    text("I'm stressed about my exams")
    with db.tx() as c:
        bodies = [r[0] for r in c.execute("select body_enc from messages")]
    assert bodies and all("exams" not in b for b in bodies)


def test_crisis_reply_case_and_alert(gateway):
    text("I want to kill myself")
    (reply,) = replies(gateway)
    assert "999" in reply and "1199" in reply
    (case,) = db.list_cases()
    assert case["tier"] == "crisis"
    (alert,) = alerts(gateway)
    assert f"#{case['id']}" in alert and "kill" not in alert and phone not in alert


def test_repeat_crisis_messages_do_not_spam_counselors(gateway):
    text("I want to kill myself")
    text("I want to die")
    assert len(db.list_cases()) == 1
    assert len(alerts(gateway)) == 1


def test_safeguarding(gateway):
    text("my husband beats me")
    assert "1195" in replies(gateway)[0]
    assert db.list_cases()[0]["tier"] == "safeguarding"


def test_safety_question_yes_escalates(gateway):
    text("I'm tired of living")
    assert "thoughts of ending your life" in replies(gateway)[-1]
    text("yes")
    assert db.list_cases()[0]["tier"] == "crisis"
    assert "999" in replies(gateway)[-1]


def test_safety_question_no_supports(gateway):
    text("I'm tired of living")
    text("No")
    assert replies(gateway)[-1].startswith("Thank you for answering honestly.")
    assert db.list_cases() == []


def test_safety_question_yes_with_more_words_escalates(gateway):
    for answer in ("yes i am", "Ndio nataka", "yes. every day"):
        db.delete_user_data(uh())
        text("I'm tired of living")
        text(answer)
        assert db.list_cases()[0]["tier"] == "crisis", answer
        assert "999" in replies(gateway)[-1]


def test_safety_question_no_with_more_words_supports(gateway):
    text("I'm tired of living")
    text("hapana asante")
    assert replies(gateway)[-1].startswith("Thank you for answering honestly.")
    assert db.list_cases() == []


def test_safety_question_no_with_crisis_words_still_escalates(gateway):
    text("I'm tired of living")
    text("no but i want to kill myself")
    assert db.list_cases()[0]["tier"] == "crisis"


def test_swahili_message_gets_swahili_reply(gateway):
    text("Nimechoka sana na kazi yangu")
    assert replies(gateway)[0].startswith("Asante kwa kutueleza.")
    assert db.get_user(uh())["language"] == "sw"


def test_keywords(gateway):
    text("HELP")
    assert "Red Cross 1199 (free)" in replies(gateway)[-1]
    text("msaada")
    assert "Red Cross 1199 (bure)" in replies(gateway)[-1]
    text("Calm!")
    assert "BREATHING" in replies(gateway)[-1]


def test_call_keyword_records_consent_and_alerts(gateway):
    text("CALL")
    assert db.get_user(uh())["callback_consent"] == 1
    assert db.list_cases()[0]["tier"] == "elevated"
    assert alerts(gateway) and "CALLBACK" in alerts(gateway)[0]


def test_delete_needs_confirmation(gateway):
    text("I'm stressed")
    text("DELETE")
    text("no")
    assert db.get_user(uh()) is not None
    text("DELETE")
    text("YES")
    assert db.get_user(uh()) is None
    with db.tx() as c:
        assert c.execute("select count(*) from messages").fetchone()[0] == 0
    assert "deleted" in gateway.sent[-1][1]


def test_delete_accepts_a_short_yes(gateway):
    text("I'm stressed")
    text("DELETE")
    text("yes please")
    assert db.get_user(uh()) is None


def test_delete_ignores_a_long_reply_starting_with_yes(gateway):
    text("I'm stressed")
    text("DELETE")
    text("yes but first tell me what happens to my case")
    assert db.get_user(uh()) is not None


def test_persistent_distress_opens_case(gateway):
    for _ in range(3):
        text("I feel hopeless")
    (case,) = db.list_cases()
    assert case["tier"] == "elevated" and "Persistent" in case["reason"]
    # elevated cases wait in the queue without paging anyone
    assert alerts(gateway) == []


def test_rate_limit_spares_crisis(gateway, monkeypatch):
    monkeypatch.setenv("MAX_REPLIES_PER_HOUR", "2")
    reload_settings()
    for _ in range(5):
        text("hello there")
    # two replies and one we will reply soon notice
    assert len(replies(gateway)) == 3
    text("I want to kill myself")
    assert "999" in replies(gateway)[-1]
