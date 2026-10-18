from dataclasses import dataclass, field

from app import content, db
from app.config import get_settings
from app.escalation import escalate
from app.gateway import send_to_user

# the ussd menu as a state machine that replays the whole keypress path
# africa's talking sends every key pressed so far on each request, like 3*1*2*4
# states are tuples that never change, so 0 for back is a stack pop and 00 jumps home
# side effects run only for the screen the last key just reached, so replaying a path never repeats them

main_menu = ("main",)
main_options = {"1": ("sms_start",), "2": ("calm",), "3": ("checkin_intro",), "4": ("urgent",), "5": ("lang",), "6": ("privacy",)}

# screens that close the session
end_screens = {"sms_start", "calm_sms", "calm_done", "urgent_sms", "callback_done", "deleted"}

exercise_steps = len(content.ussd_copy["breath"]["en"])

# the gsm limit is 182 but some handsets cut off earlier
ussd_max_chars = 160


def transition(state, key):
    # where a key press leads from this screen, None when the key means nothing here
    node = state[0]
    if node in ("main", "lang_set"):
        return main_options.get(key)
    if node == "calm":
        return {"1": ("breath", 0), "2": ("ground", 0), "3": ("calm_sms",)}.get(key)
    if node in ("breath", "ground") and key == "1":
        step = state[1] + 1
        return (node, step) if step < exercise_steps else ("calm_done",)
    if node == "checkin_intro" and key == "1":
        return ("checkin",)
    if node == "checkin":
        answers = state[1:]
        if len(answers) < 4:
            return ("checkin", *answers, int(key) - 1) if key in ("1", "2", "3", "4") else None
        return {"1": ("checkin_result", *answers, 1), "2": ("checkin_result", *answers, 0)}.get(key)
    if node == "checkin_result":
        # the last value is 1 when they said yes to the safety question
        if state[-1]:
            return {"1": ("callback_confirm", "crisis"), "2": ("urgent_sms",)}.get(key)
        return {"1": ("calm",), "2": ("sms_start",), "3": ("callback_confirm", "elevated")}.get(key)
    if node == "urgent":
        return {"1": ("callback_confirm", "crisis"), "2": ("urgent_sms",)}.get(key)
    if node == "callback_confirm":
        return {"1": ("callback_done", state[1]), "2": main_menu}.get(key)
    if node == "lang":
        return {"1": ("lang_set", "en"), "2": ("lang_set", "sw")}.get(key)
    if node == "privacy" and key == "1":
        return ("delete_confirm",)
    if node == "delete_confirm":
        return {"1": ("deleted",), "2": main_menu}.get(key)
    return None


# where a replayed path ends up
@dataclass
class walk_result:
    state: tuple
    # true when the last key moved forward into this screen
    entered: bool
    invalid: bool


def walk(path):
    stack = [main_menu]
    entered = invalid = False
    for key in path.split("*") if path else []:
        key = key.strip()
        entered = invalid = False
        if key == "00":
            stack = [main_menu]
        elif key == "0" and len(stack) > 1:
            stack.pop()
        else:
            nxt = transition(stack[-1], key)
            if nxt is None:
                invalid = True
            elif nxt == main_menu:
                stack = [main_menu]
            else:
                stack.append(nxt)
                entered = True
    return walk_result(stack[-1], entered, invalid)


def phq4_band(score):
    if score <= 2:
        return "low"
    if score <= 5:
        return "mild"
    if score <= 8:
        return "moderate"
    return "severe"


def render(state, lang):
    # returns the screen text and whether the session ends
    s = get_settings()
    u = lambda key: content.ussd(key, lang)  # noqa: E731
    emergency = content.emergency_number()
    node = state[0]

    if node == "main":
        return u("main"), False
    if node == "lang_set":
        return content.ussd("lang_set", state[1]) + content.ussd("main", state[1]), False
    if node in ("breath", "ground"):
        return u(node)[state[1]], False
    if node == "checkin":
        answers = state[1:]
        if len(answers) < 4:
            label = u("checkin_q_label").format(n=len(answers) + 1)
            return f"{label}{u('checkin_questions')[len(answers)]}\n{u('checkin_options')}", False
        return u("checkin_safety"), False
    if node == "checkin_result":
        if state[-1]:
            lines = content.helplines(content.ussd_crisis_lines, lang, mark_free=False)
            return u("checkin_safety_yes").format(emergency=emergency, lines=lines), False
        band = phq4_band(sum(state[1:5]))
        return u("checkin_band")[band] + u("checkin_band_options"), False
    if node == "urgent":
        lines = content.helplines(content.ussd_urgent_lines, lang, mark_free=False)
        return u("urgent").format(emergency=emergency, lines=lines), False
    if node == "privacy":
        return u("privacy").format(days=s.retention_days), False
    text = u(node).format(emergency=emergency, code=s.ussd_code)
    return text, node in end_screens


# what goes back to africa's talking, plus work to do after the reply is sent
@dataclass
class ussd_result:
    text: str
    end: bool
    followups: list = field(default_factory=list)

    @property
    def body(self):
        return ("END " if self.end else "CON ") + self.text


def on_enter(state, user, lang):
    # side effects for reaching a screen
    # database writes happen now, sms and counselor alerts come back as followups
    # so the ussd reply goes out first, operators drop sessions that answer slowly
    uh = user["user_hash"]
    node = state[0]
    if node == "lang_set":
        db.update_user(uh, language=state[1])
    elif node == "sms_start":
        db.record_event("sms_start", channel="ussd")
        return [lambda: send_to_user(uh, content.sms("welcome", lang))]
    elif node == "calm_sms":
        return [lambda: send_to_user(uh, content.sms("exercises", lang))]
    elif node == "calm_done":
        db.record_event("exercise", channel="ussd")
    elif node == "urgent":
        db.record_event("help_requested", channel="ussd")
    elif node == "urgent_sms":
        lines = content.helplines(content.help_lines, lang)
        return [lambda: send_to_user(uh, content.sms("help", lang, lines=lines))]
    elif node == "checkin_result":
        score, safety_yes = sum(state[1:5]), bool(state[-1])
        db.save_checkin(uh, score, safety_yes)
        db.record_event("checkin", tier="crisis" if safety_yes else phq4_band(score), channel="ussd")
    elif node == "callback_done":
        db.update_user(uh, callback_consent=1)
        tier = state[1]
        return [lambda: escalate(uh, tier, "ussd", "Asked for a counselor to call (USSD)", callback=True)]
    elif node == "deleted":
        db.delete_user_data(uh)
    return []


def handle_ussd(phone, path):
    user = db.get_or_create_user(phone)
    w = walk(path or "")
    lang = w.state[1] if w.state[0] == "lang_set" else user["language"]
    followups = on_enter(w.state, user, lang) if w.entered else []
    text, end = render(w.state, lang)
    # only show the invalid choice note when it still fits on the screen
    if w.invalid and len(content.ussd("invalid", lang) + text) <= ussd_max_chars:
        text = content.ussd("invalid", lang) + text
    if not path:
        db.record_event("ussd_session", channel="ussd")
    return ussd_result(text, end, followups)
