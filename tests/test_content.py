import itertools

import pytest

from app import content, ussd


def _all_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _all_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_strings(v)


@pytest.mark.parametrize(
    "s", list(_all_strings([content.sms_copy, content.ussd_copy, content.general_tips, content.topic_tips]))
)
def test_all_copy_is_gsm7(s):
    bad = [ch for ch in s if ch not in content.gsm7_chars]
    assert not bad, f"non-GSM-7 characters {bad!r} in: {s[:60]}"


def test_every_message_is_translated():
    for table in (content.sms_copy, content.ussd_copy, *content.general_tips, *content.topic_tips.values()):
        if "en" in table:
            assert set(table) == {"en", "sw"}
        else:
            for key, value in table.items():
                assert set(value) == {"en", "sw"}, key


def _reachable_states():
    # walks every ussd screen that can be reached from the main menu
    seen, frontier = set(), [ussd.main_menu]
    while frontier:
        state = frontier.pop()
        if state in seen:
            continue
        seen.add(state)
        for key in ["1", "2", "3", "4", "5", "6"]:
            nxt = ussd.transition(state, key)
            if nxt and nxt not in seen:
                frontier.append(nxt)
    return seen


def test_ussd_tree_is_large_enough_to_be_meaningful():
    nodes = {s[0] for s in _reachable_states()}
    assert {"main", "breath", "ground", "checkin", "checkin_result", "urgent", "callback_done", "deleted"} <= nodes


@pytest.mark.parametrize("lang", ["en", "sw"])
def test_every_ussd_screen_fits(lang):
    for state in _reachable_states():
        text, _ = ussd.render(state, lang)
        assert len(text) <= ussd.ussd_max_chars, f"{state} is {len(text)} chars in {lang}:\n{text}"
        assert content.is_gsm7(text), state


@pytest.mark.parametrize("lang,key", list(itertools.product(["en", "sw"], ["crisis", "safeguarding", "help"])))
def test_safety_messages_render_with_helplines(lang, key):
    msg = content.sms(key, lang, lines=content.helplines(content.help_lines, lang))
    assert "999" in msg and "1199" in msg
    assert content.is_gsm7(msg)


def _segments(msg):
    return 1 if len(msg) <= 160 else -(-len(msg) // 153)


@pytest.mark.parametrize("lang", ["en", "sw"])
def test_sms_cost_budget(lang):
    # the sponsor pays per segment
    # frequent messages get one, support replies two, and crisis replies may use three so they stay complete
    one = ["welcome", "menu", "safety_question", "callback", "stop", "confirm_delete", "deleted", "rate_limited"]
    for key in one:
        assert _segments(content.sms(key, lang)) == 1, key
    longest_tip = max((t[lang] for t in [*content.general_tips, *content.topic_tips.values()]), key=len)
    assert _segments(content.sms("routine", lang, tip=longest_tip)) <= 2
    assert _segments(content.sms("elevated", lang, tip=longest_tip)) <= 2
    for key in ["crisis", "safeguarding", "help"]:
        assert _segments(content.sms(key, lang, lines=content.helplines(content.help_lines, lang))) <= 3, key
