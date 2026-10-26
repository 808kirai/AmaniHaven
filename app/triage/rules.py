import re
from dataclasses import dataclass, field

# offline risk rules, the floor of the triage engine
# they run on every message, need no network and never fail, so the safety net holds when the llm is slow or off
# tuned to catch crisis language even at the cost of false alarms, a false alarm costs minutes and a miss can cost a life
# clinicians and native kiswahili and sheng speakers must review this word list before launch, and again once real traffic comes in

tiers = ("routine", "elevated", "safeguarding", "crisis")
tier_rank = {t: i for i, t in enumerate(tiers)}


# the verdict for one message
@dataclass
class triage_result:
    tier: str = "routine"
    topics: list = field(default_factory=list)
    signals: list = field(default_factory=list)
    ask_safety_question: bool = False
    reason: str = ""
    source: str = "rules"


def _rx(*patterns):
    return [re.compile(p) for p in patterns]


crisis_patterns = _rx(
    # english
    r"\bkill(ing)? my ?self\b",
    r"\bsuicid\w*",
    r"\bend(ing)? (it all|my life|everything|this life)\b",
    r"\btake my (own )?life\b",
    r"\b(want|wanna|ready) (to )?die\b",
    r"\bwish i (was|were) dead\b",
    r"\bbetter off dead\b",
    r"\bno reason to (live|go on)\b",
    r"\b(dont|do not) want to (live|be alive|wake up)\b",
    r"\bhang(ing)? my ?self\b",
    r"\boverdos\w*",
    r"\b(cut|cutting|hurt|hurting|harm|harming|burn|burning) my ?self\b",
    r"\bself ?harm\w*",
    r"\bcan ?t go on\b",
    r"\bjump(ing)? (off|from) (a|the) (bridge|building|roof)\b",
    r"\b(drink|drank|take|took|swallow\w*) (the )?(poison|pills|rat poison)\b",
    # kiswahili, jiua and jiue mean kill oneself, jinyonga hang oneself, jidhuru harm oneself, jikata cut oneself
    r"\b\w*jiu[ae]\b",
    r"\b\w*jinyong\w*",
    r"\b\w*jidhuru\b",
    r"\b\w*jikat[ae]\b",
    r"\bnataka kufa\b",
    r"\bsitaki kuishi\b",
    r"\bsina sababu ya kuishi\b",
    r"\b(kunywa|nimekunywa|nitakunywa) sumu\b",
    r"\bheri nife\b",
)

# passive death wishes are not an emergency on their own
# they always trigger the direct safety question, and asking does not raise risk
passive_patterns = _rx(
    r"\btired of (living|life|being alive)\b",
    r"\b(no point|pointless) (in )?(living|life)\b",
    r"\blife (is|feels) (pointless|meaningless)\b",
    r"\blife has no meaning\b",
    r"\bwish i (wasn ?t|was not|werent|were not) (born|here|alive)\b",
    r"\b(nobody|no one) would (miss|care if) me\b",
    r"\b(i am|im|i m) a burden\b",
    r"\bdisappear forever\b",
    r"\bnimechoka (na maisha|kuishi)\b",
    r"\bmaisha (hayana|haina) (maana|thamani)\b",
    r"\bningependa kufa\b",
    r"\bbora nife\b",
    # im dying on its own is unclear, so ask, but leave out the everyday jokes
    r"\b(i am|im|i m) (dying|going to die)\b(?! (of|from|to|for) (laugh\w*|boredom|curiosity|embarrassment|see|know|hear|try))",
    r"\bfeel(s|ing)? like dying\b",
    r"\b(ni)?nakufa\b(?! (kicheko|na kicheko|njaa))",
    r"\b(nahisi|najisikia) (kama )?(kufa|ninakufa)\b",
)

# abuse, violence and threats against the person
safeguarding_patterns = _rx(
    r"\b(he|she|they|husband|wife|father|dad|mother|mum|mom|uncle|aunt|boss|teacher|partner|boyfriend|"
    r"girlfriend|stepfather|stepmother) (beats|hits|beat|hit|rapes|raped|touches|touched|chokes|choked|"
    r"burns|burned|threatens|threatened) me\b",
    r"\braped?\b",
    r"\b(sexually )?(abused|assaulted|molested|defiled) me\b",
    r"\b(was|am|being|been|got|get) (sexually )?(abused|assaulted|molested|defiled|raped|beaten)\b",
    r"\bdefilement\b",
    r"\b(he|she) (will|is going to|wants to) kill me\b",
    # kiswahili, ananipiga means beats me, bakwa raped, nyanyasa abuse
    r"\b(a|wa)nanipiga\b",
    r"\b(a|wa)linipiga\b",
    r"\b\w*bakwa\b",
    r"\b(a|wa)(li)?nibaka\b",
    r"\b\w*nyanyas\w*",
    r"\bananitishia\b",
    r"\b(a|wa)taniua\b",
)

# real distress without crisis signs
elevated_patterns = _rx(
    r"\bhopeless\w*",
    r"\bworthless\b",
    r"\bempty inside\b",
    r"\bcan ?t cope\b",
    r"\bpanic attack\w*",
    r"\bcan ?t breathe\b",
    r"\bdepress(ed|ion)\b",
    r"\bcan ?t stop crying\b",
    r"\b(nobody|no one) cares\b",
    r"\b(all|so|completely) alone\b",
    r"\bgiv(e|ing) up\b",
    r"\bfalling apart\b",
    r"\bbreaking down\b",
    r"\bsina tumaini\b",
    r"\bnimekata tamaa\b",
    r"\bsina thamani\b",
    r"\bhakuna (anayejali|mtu anajali)\b",
    r"\bnalia kila (siku|wakati)\b",
    r"\bhuzuni (nyingi|sana)\b",
    r"\bsiwezi (tena|kuvumilia)\b",
)

# what the message is about, used to pick a fitting tip
topic_patterns = {
    "sleep": _rx(r"\b(sleep\w*|insomnia|awake all night|usingizi|silali|sipati usingizi)\b"),
    "stress": _rx(
        r"\b(stress\w*|pressure|overwhelm\w*|exams?|kcse|kcpe|msongo|presha|mtihani|mitihani|shule|chuo)\b"
    ),
    "loneliness": _rx(r"\b(lonely|loneliness|alone|no friends|isolated|upweke|peke yangu)\b"),
    "grief": _rx(
        r"\b(died|passed away|death|funeral|grief|griev\w*|lost my|msiba|amefariki|alifariki|alikufa|kifo|kufiwa)\b"
    ),
    "relationships": _rx(
        r"\b(boyfriend|girlfriend|husband|wife|marriage|married|break ?up|broke up|divorce|cheat\w*|"
        r"mpenzi|mume|mke|ndoa|ameniacha|aliniacha)\b"
    ),
    "money": _rx(
        r"\b(money|jobless|unemployed|no job|lost my job|debt|loan|rent|school fees|fees|bills|"
        r"pesa|sina kazi|deni|mkopo|karo|kodi)\b"
    ),
    "anxiety": _rx(r"\b(anxious|anxiety|panic\w*|worr(y|ied|ying)|nervous|scared|afraid|wasiwasi|hofu|woga)\b"),
    "substance": _rx(r"\b(alcohol|drunk|drinking|weed|bhang|drugs|addict\w*|pombe|bangi|dawa za kulevya|chang aa)\b"),
}

negators = {"not", "never", "no", "dont", "wont", "wouldnt", "isnt", "aint"}

# a negation only counts inside its own clause, so i'm not ok but i want to die still reads as crisis
clause_break = re.compile(r"[.!?;,\n]|\bbut\b|\blakini\b|\bila\b")


def normalize(text, max_repeat=2):
    # lowercase, drop punctuation and squash stretched letters like dieeee
    text = text.lower().replace("’", "'").replace("`", "'").replace("n't", "nt")
    text = re.sub(r"(.)\1{2,}", r"\1" * max_repeat, text)
    text = re.sub(r"[^a-z0-9'\s]", " ", text)
    text = text.replace("'", " ")
    return re.sub(r"\s+", " ", text).strip()


def _variants(text):
    # squashing stretched letters to two keeps killll as kill, squashing to one keeps dieeee as die
    # so both versions are checked
    return list(dict.fromkeys(v for v in (normalize(text, 2), normalize(text, 1)) if v))


def _find(patterns, texts):
    hits = []
    for rx in patterns:
        for t in texts:
            if m := rx.search(t):
                hits.append(m.group(0))
                break
    return hits


def _negated(clause, start):
    # looks at the three words before the match
    preceding = clause[:start].split()[-3:]
    return any(w in negators for w in preceding)


def assess(text):
    result = triage_result()
    raw = text or ""

    # crisis words are checked clause by clause so a negation can't reach across a sentence
    crisis_hits, negated_hits = [], []
    for raw_clause in clause_break.split(raw.lower()):
        for rx in crisis_patterns:
            for clause in _variants(raw_clause):
                if m := rx.search(clause):
                    (negated_hits if _negated(clause, m.start()) else crisis_hits).append(m.group(0))
                    break

    texts = _variants(raw)
    passive = _find(passive_patterns, texts)
    safeguarding = _find(safeguarding_patterns, texts)
    elevated = _find(elevated_patterns, texts)
    result.topics = [topic for topic, patterns in topic_patterns.items() if _find(patterns, texts)]

    if crisis_hits:
        result.tier = "crisis"
        result.signals = crisis_hits
        result.reason = "Crisis language: " + ", ".join(sorted(set(crisis_hits)))
    elif safeguarding:
        result.tier = "safeguarding"
        result.signals = safeguarding
        result.reason = "Possible abuse or violence: " + ", ".join(sorted(set(safeguarding)))
    elif negated_hits or passive:
        # i'm not suicidal is usually true, but sometimes it is how people test the water
        # so neither escalate nor dismiss it, ask directly
        result.tier = "elevated"
        result.ask_safety_question = True
        result.signals = negated_hits + passive
        result.reason = "Possible ideation, needs safety check: " + ", ".join(sorted(set(result.signals)))
    elif elevated:
        result.tier = "elevated"
        result.signals = elevated
        result.reason = "Distress: " + ", ".join(sorted(set(elevated)))
    return result


# common words used to guess which language a message is in
sw_words = {
    "na", "ya", "wa", "kwa", "ni", "sana", "nina", "sina", "mimi", "wewe", "yangu", "nataka", "sitaki",
    "lakini", "kwamba", "hii", "kila", "siku", "kuna", "hakuna", "nini", "je", "tu", "pia", "bado",
    "sijui", "naomba", "habari", "asante", "leo", "maisha", "mtu", "watu", "nyumbani", "kazi", "sawa",
    "sasa", "hapa", "kama", "niko", "uko", "yuko", "ndio", "hapana", "siwezi", "nimechoka", "msaada",
}
en_words = {
    "i", "the", "and", "to", "is", "am", "my", "me", "you", "it", "of", "not", "feel", "have", "so",
    "very", "just", "want", "life", "what", "how", "im", "dont", "can", "this", "that", "with", "help",
}


def detect_language(text):
    # returns sw, en or None when it can't tell
    words = normalize(text).split()
    sw = sum(w in sw_words or w.startswith(("nime", "nita", "sija", "kuj")) for w in words)
    en = sum(w in en_words for w in words)
    if sw > en:
        return "sw"
    if en > sw:
        return "en"
    return None
