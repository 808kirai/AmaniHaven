import pytest

from app.triage.rules import assess, detect_language


@pytest.mark.parametrize(
    "text",
    [
        "I want to kill myself",
        "i wanna die",
        "I want to dieeee",
        "thinking about suicide",
        "I'm going to end it all tonight",
        "I took the pills",
        "I keep cutting myself",
        "Nataka kujiua",
        "nitajiua leo",
        "nataka kufa",
        "Sitaki kuishi tena",
        "nimekunywa sumu",
        "I am fine. But I don't want to live anymore",
    ],
)
def test_crisis_language(text):
    assert assess(text).tier == "crisis"


@pytest.mark.parametrize(
    "text",
    [
        "I'm not suicidal, just stressed",
        "I would never kill myself",
        "I don't want to die but I'm so tired",
    ],
)
def test_negated_crisis_asks_safety_question(text):
    r = assess(text)
    assert r.tier == "elevated"
    assert r.ask_safety_question


@pytest.mark.parametrize(
    "text",
    [
        "I'm tired of living", "nobody would miss me", "Nimechoka na maisha", "life has no meaning",
        "im dying help mee", "I am dying", "I feel like dying", "nakufa", "ninakufa", "nahisi kufa",
    ],
)
def test_passive_ideation_asks_safety_question(text):
    r = assess(text)
    assert r.tier == "elevated"
    assert r.ask_safety_question


@pytest.mark.parametrize(
    "text",
    ["My husband beats me every night", "I was raped", "Baba ananipiga", "nilibakwa", "my uncle touched me"],
)
def test_safeguarding(text):
    assert assess(text).tier == "safeguarding"


@pytest.mark.parametrize("text", ["I feel hopeless", "I can't cope anymore", "sina tumaini", "nimekata tamaa"])
def test_elevated(text):
    r = assess(text)
    assert r.tier == "elevated"
    assert not r.ask_safety_question


@pytest.mark.parametrize(
    "text",
    [
        "I'm stressed about exams", "this exam is killing me", "hello", "sina pesa ya karo", "I can't sleep",
        "im dying of laughter", "I'm dying to see the new film", "nakufa kicheko",
    ],
)
def test_routine(text):
    assert assess(text).tier == "routine"


def test_crisis_outranks_safeguarding():
    assert assess("he beats me and I want to kill myself").tier == "crisis"


def test_topics():
    assert "stress" in assess("so much pressure from exams").topics
    assert "sleep" in assess("silali usiku").topics
    assert "money" in assess("I lost my job and the rent is due").topics


def test_detect_language():
    assert detect_language("Nimechoka sana na kazi") == "sw"
    assert detect_language("I feel so tired of my job") == "en"
    assert detect_language("ok") is None
