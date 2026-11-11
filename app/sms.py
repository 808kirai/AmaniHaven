import logging
import re
from datetime import timedelta

from app import content, db
from app.config import get_settings
from app.escalation import escalate
from app.gateway import get_gateway, send_to_user
from app.privacy import decrypt, normalize_msisdn
from app.triage.engine import triage
from app.triage.rules import assess, detect_language

log = logging.getLogger(__name__)

# the two way sms conversation
# answers to our own questions come first, then keywords, then triage of free text

yes_words = {"YES", "Y", "YEAH", "YEP", "NDIO", "NDIYO", "EE", "EEH", "EH"}
no_words = {"NO", "N", "NOPE", "HAPANA", "APANA", "LA"}

# whole message keywords, each mapped to an action and the language to reply in
keywords = {
    "MENU": ("menu", "en"), "ORODHA": ("menu", "sw"), "CHAGUO": ("menu", "sw"),
    "HELP": ("help", "en"), "SOS": ("help", "en"), "MSAADA": ("help", "sw"), "DHARURA": ("help", "sw"),
    "CALM": ("calm", "en"), "TULIA": ("calm", "sw"),
    "CALL": ("call", "en"), "CALLME": ("call", "en"), "NIPIGIE": ("call", "sw"),
    "STOP": ("stop", "en"), "ACHA": ("stop", "sw"),
    "START": ("start", "en"), "ANZA": ("start", "sw"),
    "DELETE": ("delete", "en"), "FUTA": ("delete", "sw"),
    "EN": ("lang", "en"), "ENGLISH": ("lang", "en"),
    "SW": ("lang", "sw"), "KISWAHILI": ("lang", "sw"), "SWAHILI": ("lang", "sw"),
}


def _keyword(text):
    # only short messages count, so help me i want to die is triaged instead of treated as HELP
    if len(text) > 15:
        return ""
    return re.sub(r"[^A-Z]", "", text.upper())


def _answer(text, max_words=None):
    # yes or no from the first word, so yes i am and hapana asante both count
    # returns None when the reply doesn't start with either
    words = re.findall(r"[A-Za-z]+", text.upper())
    if not words or (max_words and len(words) > max_words):
        return None
    if words[0] in yes_words:
        return "yes"
    if words[0] in no_words:
        return "no"
    return None


def _next_tip(user, topics, lang):
    # topic tips first, then the general ones, rotating so nobody gets the same tip twice in a row
    candidates = [content.topic_tips[t] for t in topics if t in content.topic_tips] + content.general_tips
    cursor = user["tip_cursor"]
    db.update_user(user["user_hash"], tip_cursor=cursor + 1)
    return candidates[cursor % len(candidates)][lang]


async def _keyword_action(user, action, lang):
    uh = user["user_hash"]
    if action == "menu":
        await send_to_user(uh, content.sms("menu", lang))
    elif action == "help":
        db.record_event("help_requested", channel="sms")
        await send_to_user(uh, content.sms("help", lang, lines=content.helplines(content.help_lines, lang)))
    elif action == "calm":
        db.record_event("exercise", channel="sms")
        await send_to_user(uh, content.sms("exercises", lang))
    elif action == "call":
        db.update_user(uh, callback_consent=1)
        await escalate(uh, "elevated", "sms", "Asked for a counselor to call", callback=True)
        await send_to_user(uh, content.sms("callback", lang))
    elif action == "stop":
        db.update_user(uh, opted_out=1)
        await send_to_user(uh, content.sms("stop", lang))
    elif action == "start":
        db.update_user(uh, opted_out=0)
        await send_to_user(uh, content.sms("start", lang))
    elif action == "delete":
        db.update_user(uh, pending_state="confirm_delete")
        await send_to_user(uh, content.sms("confirm_delete", lang))
    elif action == "lang":
        db.update_user(uh, language=lang)
        await send_to_user(uh, content.sms("language_set", lang))


async def _crisis(uh, tier, lang, reason):
    await escalate(uh, tier, "sms", reason)
    lines = content.crisis_lines if tier == "crisis" else content.safeguarding_lines
    await send_to_user(uh, content.sms(tier, lang, lines=content.helplines(lines, lang)))


async def handle_inbound_sms(phone, text):
    user = db.get_or_create_user(phone)
    uh, lang = user["user_hash"], user["language"]
    text = (text or "").strip()
    if not text:
        return
    word = _keyword(text)

    # answers to a question we asked in the last message
    pending = user["pending_state"]
    if pending:
        db.update_user(uh, pending_state=None)
    # deleting can't be undone, so only a short reply counts
    delete_answer = _answer(text, max_words=3)
    safety_answer = _answer(text)
    if pending == "confirm_delete" and delete_answer == "yes":
        db.delete_user_data(uh)
        # the thread is gone now, so send directly without keeping a copy
        await get_gateway().send(normalize_msisdn(phone), content.sms("deleted", lang))
        return
    if pending == "confirm_delete" and delete_answer == "no":
        db.save_message(uh, "in", "sms", text)
        await send_to_user(uh, content.sms("kept", lang))
        return
    if pending == "safety_question" and safety_answer == "yes":
        db.save_message(uh, "in", "sms", text, tier="crisis")
        db.record_event("sms_in", tier="crisis", channel="sms")
        await _crisis(uh, "crisis", lang, "Answered YES to the direct suicide question")
        return
    # no but i want to die still goes through triage below
    if pending == "safety_question" and safety_answer == "no" and assess(text).tier not in ("crisis", "safeguarding"):
        db.save_message(uh, "in", "sms", text, tier="elevated")
        tip = _next_tip(user, [], lang)
        await send_to_user(uh, content.sms("safety_no", lang) + " " + content.sms("elevated", lang, tip=tip))
        return

    # keywords
    if word in keywords:
        action, kw_lang = keywords[word]
        db.save_message(uh, "in", "sms", text)
        await _keyword_action(user, action, kw_lang)
        return

    # free text, reply in the language they wrote in and then triage it
    detected = detect_language(text)
    if detected and detected != lang:
        lang = detected
        db.update_user(uh, language=lang)
    history = [decrypt(m["body_enc"]) or "" for m in db.recent_messages(uh, 6) if m["direction"] == "in"]
    result = await triage(text, history)
    db.save_message(uh, "in", "sms", text, tier=result.tier)
    db.record_event("sms_in", tier=result.tier, channel="sms")
    # writing to us counts as opting back in
    if user["opted_out"]:
        db.update_user(uh, opted_out=0)

    if result.tier in ("crisis", "safeguarding"):
        await _crisis(uh, result.tier, lang, result.reason)
        return

    if result.ask_safety_question:
        db.update_user(uh, pending_state="safety_question")
        await send_to_user(uh, content.sms("safety_question", lang))
        return

    # cost guard for routine and elevated replies, crisis replies above are never limited
    sent = db.outbound_count_since(uh, timedelta(hours=1))
    limit = get_settings().max_replies_per_hour
    if sent > limit:
        return
    if sent == limit:
        await send_to_user(uh, content.sms("rate_limited", lang))
        return

    tip = _next_tip(user, result.topics, lang)
    if result.tier == "elevated":
        # repeated distress gets a case in the queue without paging anyone
        if db.inbound_tier_count_since(uh, "elevated", timedelta(hours=24)) >= 3:
            await escalate(uh, "elevated", "sms", "Persistent distress: 3+ distressed messages in 24h")
        await send_to_user(uh, content.sms("elevated", lang, tip=tip))
    else:
        await send_to_user(uh, content.sms("routine", lang, tip=tip))
