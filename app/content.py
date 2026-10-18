from app.config import get_settings

# every word amanihaven says to a user lives in this file
# so a clinician and a kiswahili speaker can review the whole product in one sitting
# nothing here is written by a model at runtime, people in distress get reviewed wording
# tests keep all of it to gsm 7 characters, since one emoji or curly quote cuts an sms from 160 to 70 characters
# tests also keep every ussd screen within 160 characters

langs = ("en", "sw")


# helplines


def helplines(keys, lang, mark_free=True):
    # names and numbers in one line, with the free ones marked
    # pass mark_free=False when the screen already says every line is free
    by_key = {h.key: h for h in get_settings().helplines}
    free = " (bure)" if lang == "sw" else " (free)"
    parts = []
    for k in keys:
        h = by_key.get(k)
        if h:
            name = h.name_sw if lang == "sw" else h.name_en
            parts.append(f"{name} {h.number}{free if h.free and mark_free else ''}")
    return ", ".join(parts)


def emergency_number():
    for h in get_settings().helplines:
        if h.key == "emergency":
            return h.number
    return "112"


# sms replies

sms_copy = {
    "welcome": {
        "en": "Welcome to AmaniHaven. This is a free, private space to talk. Tell us how you are feeling, "
        "in your own words. Reply MENU for options. In danger? Call {emergency}.",
        "sw": "Karibu AmaniHaven. Hapa ni mahali salama na bure pa kuongea kwa siri. Tuambie unavyohisi "
        "kwa maneno yako. Jibu ORODHA kwa chaguo. Uko hatarini? Piga {emergency}.",
    },
    "menu": {
        "en": "AmaniHaven (free):\nCALM - calming exercise\nHELP - urgent numbers\n"
        "CALL - a counselor calls you\nSW - Kiswahili\nDELETE - erase your data\nSTOP - stop messages",
        "sw": "AmaniHaven (bure):\nTULIA - zoezi la kutuliza\nMSAADA - nambari za dharura\n"
        "NIPIGIE - mshauri akupigie\nEN - English\nFUTA - futa data yako\nACHA - usitumiwe ujumbe",
    },
    "crisis": {
        "en": "Thank you for telling us. Your life matters and you do not have to face this alone. "
        "If you are in danger now, call {emergency}. To talk now: {lines}. "
        "A counselor from our team will text you here as soon as possible. Reply CALL for a phone call.",
        "sw": "Asante kwa kutueleza. Maisha yako yana thamani na hauko peke yako. "
        "Ukiwa hatarini sasa, piga {emergency}. Kuongea sasa: {lines}. "
        "Mshauri wetu atakutumia ujumbe hapa haraka iwezekanavyo. Jibu NIPIGIE upigiwe simu.",
    },
    "safeguarding": {
        "en": "Thank you for trusting us. What is happening to you is not your fault. "
        "If you are in danger now, call {emergency}. To talk now: {lines}. "
        "A counselor will text you here soon. Reply CALL for a phone call.",
        "sw": "Asante kwa kutuamini. Kinachokutokea si kosa lako. "
        "Ukiwa hatarini sasa, piga {emergency}. Kuongea sasa: {lines}. "
        "Mshauri atakutumia ujumbe hapa hivi karibuni. Jibu NIPIGIE upigiwe simu.",
    },
    "safety_question": {
        "en": "Thank you for telling us. We ask everyone this because it matters: are you having "
        "thoughts of ending your life? Reply YES or NO. Either way, we are here.",
        "sw": "Asante kwa kutueleza. Tunamuuliza kila mtu kwa sababu ni muhimu: je, una mawazo ya "
        "kujiua? Jibu NDIO au HAPANA. Jibu lolote, tuko nawe.",
    },
    "safety_no": {
        "en": "Thank you for answering honestly.",
        "sw": "Asante kwa kujibu kwa ukweli.",
    },
    "elevated": {
        "en": "That sounds really hard, and it took strength to share it. You are not alone. {tip} "
        "Reply CALL to talk to a counselor, or keep texting us.",
        "sw": "Inaonekana ni ngumu sana, na umeonyesha ujasiri kueleza. Hauko peke yako. {tip} "
        "Jibu NIPIGIE kuongea na mshauri, au endelea kutuandikia.",
    },
    "routine": {
        "en": "Thank you for sharing. {tip} Reply MENU for more.",
        "sw": "Asante kwa kutueleza. {tip} Jibu ORODHA kwa zaidi.",
    },
    "help": {
        "en": "In danger now? Call {emergency}. To talk now: {lines}. Reply CALL and a counselor will call you.",
        "sw": "Uko hatarini sasa? Piga {emergency}. Kuongea sasa: {lines}. Jibu NIPIGIE na mshauri atakupigia.",
    },
    "callback": {
        "en": "Thank you. A counselor will call you on this number as soon as one is free. "
        "If you are in danger before then, call {emergency}.",
        "sw": "Asante. Mshauri atakupigia kwenye nambari hii punde atakapopatikana. "
        "Ukiwa hatarini kabla ya hapo, piga {emergency}.",
    },
    "stop": {
        "en": "Done. We will not message you unless you text us first. We are here whenever you need us.",
        "sw": "Sawa. Hatutakutumia ujumbe isipokuwa utuandikie kwanza. Tuko hapa ukituhitaji.",
    },
    "start": {
        "en": "Welcome back. Tell us how you are feeling, any time.",
        "sw": "Karibu tena. Tuambie unavyohisi, wakati wowote.",
    },
    "confirm_delete": {
        "en": "This erases all your messages and history with us. Reply YES to delete or NO to keep.",
        "sw": "Hii itafuta ujumbe na historia yako yote kwetu. Jibu NDIO kufuta au HAPANA kubaki.",
    },
    "deleted": {
        "en": "Done. Everything is deleted. You are welcome back any time.",
        "sw": "Imekamilika. Kila kitu kimefutwa. Karibu tena wakati wowote.",
    },
    "kept": {
        "en": "Okay, nothing was deleted.",
        "sw": "Sawa, hakuna kilichofutwa.",
    },
    "language_set": {
        "en": "Language set to English. Reply SW for Kiswahili.",
        "sw": "Lugha imewekwa Kiswahili. Jibu EN kwa English.",
    },
    "rate_limited": {
        "en": "We have your messages and a counselor can read them. We will reply again soon. "
        "In danger? Call {emergency}.",
        "sw": "Tumepokea ujumbe wako na mshauri anaweza kuusoma. Tutajibu tena hivi karibuni. "
        "Uko hatarini? Piga {emergency}.",
    },
    "counselor_prefix": {
        "en": "AmaniHaven counselor: ",
        "sw": "Mshauri wa AmaniHaven: ",
    },
    "exercises": {
        "en": "CALM BREATHING: in for 4, hold for 4, out for 6. Repeat 5 times.\n"
        "GROUNDING: name 5 things you see, 4 you can touch, 3 you hear, 2 you smell, 1 you taste.",
        "sw": "KUPUMUA: vuta pumzi 4, shikilia 4, toa 6. Rudia mara 5.\n"
        "KUTULIZA: taja vitu 5 unavyoona, 4 unavyogusa, 3 unavyosikia, 2 unavyonusa, 1 unachoonja.",
    },
}

# which helplines go with each kind of reply
crisis_lines = ["redcross", "befrienders"]
safeguarding_lines = ["gbv", "child"]
help_lines = ["redcross", "gbv", "child", "befrienders"]


# self help tips
# short techniques from cbt, behavioural activation and grounding practice
# each one stands alone because people may only ever see one

general_tips = [
    {
        "en": "Try this: breathe in for 4, hold for 4, out for 4, hold for 4. Repeat 4 times. "
        "Slow breathing tells your body it is safe to calm down.",
        "sw": "Jaribu hivi: vuta pumzi hesabu 4, shikilia 4, toa 4, shikilia 4. Rudia mara 4. "
        "Kupumua polepole huambia mwili wako kwamba unaweza kutulia.",
    },
    {
        "en": "When thoughts race, name 5 things you see, 4 you can touch, 3 you hear, 2 you smell "
        "and 1 you taste. It brings you back to right now.",
        "sw": "Mawazo yakizidi, taja vitu 5 unavyoona, 4 unavyoweza kugusa, 3 unavyosikia, 2 unavyonusa "
        "na 1 unachoonja. Inakurudisha wakati huu.",
    },
    {
        "en": "Is there one person you trust - a friend, relative or faith leader? Sharing even a "
        "little with them can lighten the load.",
        "sw": "Je, kuna mtu mmoja unayemwamini - rafiki, ndugu au kiongozi wa dini? Kumweleza hata "
        "kidogo kunaweza kupunguza mzigo.",
    },
    {
        "en": "When everything feels heavy, pick one small thing to do today - drink water, step "
        "outside, wash your face. Small steps count.",
        "sw": "Mambo yakiwa mazito, chagua jambo moja dogo la kufanya leo - kunywa maji, toka nje "
        "kidogo, nawa uso. Hatua ndogo zina maana.",
    },
]

# matched to what the person wrote about
topic_tips = {
    "sleep": {
        "en": "For better sleep: keep the same sleep and wake time, put the phone away 30 minutes "
        "before bed, and avoid tea or coffee after 4pm.",
        "sw": "Ili ulale vizuri: lala na uamke saa zile zile, weka simu mbali dakika 30 kabla ya "
        "kulala, na epuka chai au kahawa baada ya saa kumi jioni.",
    },
    "stress": {
        "en": "Stress shrinks when you break it down. Write the 3 things worrying you most, then one "
        "small action for each. Start with the easiest.",
        "sw": "Msongo hupungua ukiugawa. Andika mambo 3 yanayokusumbua zaidi, kisha hatua moja ndogo "
        "kwa kila moja. Anza na rahisi zaidi.",
    },
    "loneliness": {
        "en": "Feeling alone is painful, and many people feel it too. Could you send one person a "
        "short message today, even just to say hello?",
        "sw": "Upweke unauma, na watu wengi huhisi hivyo pia. Je, unaweza kumtumia mtu mmoja ujumbe "
        "mfupi leo, hata kusalimia tu?",
    },
    "grief": {
        "en": "Grief has no timetable. It is okay to cry, to remember and to ask for help. Talking "
        "about the person you lost can ease the pain.",
        "sw": "Huzuni ya kufiwa haina ratiba. Ni sawa kulia, kukumbuka na kuomba msaada. Kumzungumzia "
        "uliyempoteza kunaweza kupunguza uchungu.",
    },
    "relationships": {
        "en": "Relationship pain can feel overwhelming. Before reacting, take 10 slow breaths, then "
        "ask: what do I need right now, and who can support me?",
        "sw": "Maumivu ya mahusiano yanaweza kulemea. Kabla ya kuchukua hatua, pumua polepole mara 10, "
        "kisha jiulize: nahitaji nini sasa, na nani anaweza kunisaidia?",
    },
    "money": {
        "en": "Money and job worries are heavy, and you are more than your situation. Focus on one "
        "next step for today, and talk it over with someone you trust.",
        "sw": "Wasiwasi wa pesa na kazi ni mzito, na wewe ni zaidi ya hali yako. Zingatia hatua moja "
        "ya leo, na uongee na mtu unayemwamini.",
    },
    "anxiety": {
        "en": "Anxiety is your body's alarm, and it passes. Breathe out more slowly than you breathe "
        "in. Feel your feet on the ground. This feeling will pass.",
        "sw": "Wasiwasi ni kengele ya mwili wako, na hupita. Toa pumzi polepole kuliko unavyovuta. "
        "Hisi miguu yako ardhini. Hisia hii itapita.",
    },
    "substance": {
        "en": "If alcohol or drugs have become a way to cope, you are not alone and help exists. "
        "Take it one day at a time.",
        "sw": "Ikiwa pombe au dawa za kulevya zimekuwa njia ya kukabiliana, hauko peke yako na msaada "
        "upo. Chukua siku moja baada ya nyingine.",
    },
}

# ussd screens, each one has to fit in 160 characters

ussd_copy = {
    "main": {
        "en": "AmaniHaven - free & private\n1. Talk by SMS\n2. Calm down now\n3. How am I feeling?\n"
        "4. Urgent help\n5. Lugha/Language\n6. Privacy",
        "sw": "AmaniHaven - bure na siri\n1. Ongea kwa SMS\n2. Tulia sasa\n3. Ninajisikiaje?\n"
        "4. Msaada wa dharura\n5. Lugha/Language\n6. Faragha",
    },
    "invalid": {"en": "Invalid choice.\n", "sw": "Chaguo si sahihi.\n"},
    "sms_start": {
        "en": "We have sent you an SMS. Reply to it any time, in your own words. It is free.",
        "sw": "Tumekutumia SMS. Ijibu wakati wowote kwa maneno yako. Ni bure.",
    },
    "calm": {
        "en": "Choose an exercise:\n1. Slow breathing\n2. 5-4-3-2-1 grounding\n3. Send exercises to my SMS\n0. Back",
        "sw": "Chagua zoezi:\n1. Kupumua polepole\n2. Kutuliza 5-4-3-2-1\n3. Nitumie mazoezi kwa SMS\n0. Rudi",
    },
    "breath": {
        "en": [
            "Sit comfortably and relax your shoulders.\nBreathe IN slowly through your nose: 1, 2, 3, 4.\n1. Next",
            "HOLD gently: 1, 2, 3, 4.\n1. Next",
            "Breathe OUT slowly through your mouth: 1, 2, 3, 4, 5, 6.\n1. Next",
            "Again: in for 4, hold for 4, out for 6. Do this 5 times at your own pace.\n1. Done",
        ],
        "sw": [
            "Kaa vizuri na ulegeze mabega.\nVuta pumzi polepole kwa pua: 1, 2, 3, 4.\n1. Endelea",
            "Shikilia taratibu: 1, 2, 3, 4.\n1. Endelea",
            "Toa pumzi polepole kwa mdomo: 1, 2, 3, 4, 5, 6.\n1. Endelea",
            "Tena: vuta 4, shikilia 4, toa 6. Fanya hivi mara 5 kwa mwendo wako.\n1. Nimemaliza",
        ],
    },
    "ground": {
        "en": [
            "Look around you. Name 5 things you can SEE.\n1. Next",
            "Notice 4 things you can TOUCH - your clothes, the chair, the ground.\n1. Next",
            "Listen for 3 things you can HEAR.\n1. Next",
            "Notice 2 things you can SMELL and 1 thing you can TASTE.\n1. Done",
        ],
        "sw": [
            "Angalia karibu nawe. Taja vitu 5 unavyoweza KUONA.\n1. Endelea",
            "Hisi vitu 4 unavyoweza KUGUSA - nguo, kiti, ardhi.\n1. Endelea",
            "Sikiliza sauti 3 unazoweza KUSIKIA.\n1. Endelea",
            "Tambua vitu 2 unavyoweza KUNUSA na 1 unachoweza KUONJA.\n1. Nimemaliza",
        ],
    },
    "calm_done": {
        "en": "Well done. Your body is calmer than it was a minute ago. Dial {code} any time.",
        "sw": "Hongera. Mwili wako umetulia kuliko dakika iliyopita. Piga {code} wakati wowote.",
    },
    "calm_sms": {
        "en": "Sent. Check your SMS - the exercises are yours to keep.",
        "sw": "Imetumwa. Angalia SMS zako - mazoezi ni yako kuweka.",
    },
    "checkin_intro": {
        "en": "4 quick questions about the last 2 weeks. Your answers are private. This is not a "
        "diagnosis.\n1. Start\n0. Back",
        "sw": "Maswali 4 mafupi kuhusu wiki 2 zilizopita. Majibu yako ni siri. Huu si uchunguzi wa "
        "kitabibu.\n1. Anza\n0. Rudi",
    },
    # the phq 4 by kroenke and colleagues 2009
    # the first two questions screen for anxiety and the last two for depression
    "checkin_questions": {
        "en": [
            "Feeling nervous, anxious or on edge?",
            "Not being able to stop or control worrying?",
            "Little interest or pleasure in doing things?",
            "Feeling down, depressed or hopeless?",
        ],
        "sw": [
            "Kuhisi hofu, wasiwasi au kutotulia?",
            "Kushindwa kuacha au kudhibiti wasiwasi?",
            "Kukosa hamu au furaha ya kufanya mambo?",
            "Kuhisi huzuni, msongo au kukosa tumaini?",
        ],
    },
    "checkin_options": {
        "en": "1. Not at all\n2. Several days\n3. More than half the days\n4. Nearly every day",
        "sw": "1. Hata kidogo\n2. Siku kadhaa\n3. Zaidi ya nusu ya siku\n4. Karibu kila siku",
    },
    "checkin_q_label": {"en": "Q{n}/4: ", "sw": "S{n}/4: "},
    # asked after the phq 4 because it has no question about suicide, unlike the phq 9
    "checkin_safety": {
        "en": "Last one: in the past 2 weeks, have you had thoughts that you would be better off "
        "dead, or of hurting yourself?\n1. Yes\n2. No",
        "sw": "La mwisho: katika wiki 2 zilizopita, umekuwa na mawazo kwamba ingekuwa heri ufe, au "
        "ya kujidhuru?\n1. Ndio\n2. Hapana",
    },
    "checkin_safety_yes": {
        "en": "Thank you for your honesty. You deserve support now.\nIn danger: call {emergency}\n"
        "Free: {lines}\n1. A counselor calls me\n2. SMS me help numbers",
        "sw": "Asante kwa ukweli wako. Unastahili msaada sasa.\nUkiwa hatarini: piga {emergency}\n"
        "Bure: {lines}\n1. Mshauri anipigie\n2. Nitumie nambari kwa SMS",
    },
    "checkin_band": {
        "en": {
            "low": "Your answers suggest you are coping well. Keep caring for yourself.",
            "mild": "Your answers suggest some stress lately. Small daily habits can help.",
            "moderate": "Your answers suggest you are carrying a lot. Talking to someone can help.",
            "severe": "Your answers suggest things are very hard right now. Please let a counselor help.",
        },
        "sw": {
            "low": "Majibu yako yanaonyesha unakabiliana vizuri. Endelea kujitunza.",
            "mild": "Majibu yako yanaonyesha msongo kidogo. Tabia ndogo za kila siku zinasaidia.",
            "moderate": "Majibu yako yanaonyesha umebeba mengi. Kuongea na mtu kunasaidia.",
            "severe": "Majibu yako yanaonyesha mambo ni magumu sana sasa. Mshauri akusaidie.",
        },
    },
    "checkin_band_options": {
        "en": "\n1. Calm exercise\n2. Talk by SMS\n3. A counselor calls me",
        "sw": "\n1. Zoezi la kutulia\n2. Ongea kwa SMS\n3. Mshauri anipigie",
    },
    "urgent": {
        "en": "In danger now? Call {emergency}.\nFree: {lines}\n1. A counselor calls me\n2. SMS me these numbers\n0. Back",
        "sw": "Uko hatarini sasa? Piga {emergency}.\nBure: {lines}\n1. Mshauri anipigie\n2. Nitumie nambari hizi\n0. Rudi",
    },
    "urgent_sms": {
        "en": "Sent. Keep these numbers safe. You can dial {code} any time.",
        "sw": "Imetumwa. Weka nambari hizi salama. Piga {code} wakati wowote.",
    },
    "callback_confirm": {
        "en": "A counselor will call this number and say they are from AmaniHaven. Is that OK?\n"
        "1. Yes, call me\n2. No",
        "sw": "Mshauri atakupigia kwenye nambari hii na kusema anatoka AmaniHaven. Ni sawa?\n"
        "1. Ndio, nipigie\n2. Hapana",
    },
    "callback_done": {
        "en": "Thank you. A counselor will call you as soon as one is free. If you are in danger, "
        "call {emergency} now.",
        "sw": "Asante. Mshauri atakupigia punde atakapopatikana. Ukiwa hatarini, piga {emergency} sasa.",
    },
    "lang": {
        "en": "Choose language / Chagua lugha:\n1. English\n2. Kiswahili",
        "sw": "Chagua lugha / Choose language:\n1. English\n2. Kiswahili",
    },
    "lang_set": {"en": "Language saved.\n", "sw": "Lugha imehifadhiwa.\n"},
    "privacy": {
        "en": "We never share your number. Messages are encrypted and deleted after {days} days. "
        "Delete our SMS if others use your phone.\n1. Delete my data\n0. Back",
        "sw": "Hatutoi nambari yako. Ujumbe husimbwa na kufutwa baada ya siku {days}. Futa SMS zetu "
        "kama wengine hutumia simu yako.\n1. Futa data\n0. Rudi",
    },
    "delete_confirm": {
        "en": "Delete all your data with us? This cannot be undone.\n1. Yes, delete\n2. No",
        "sw": "Futa data yako yote kwetu? Haiwezi kurudishwa.\n1. Ndio, futa\n2. Hapana",
    },
    "deleted": {
        "en": "Done. Everything is deleted. You are welcome back any time.",
        "sw": "Imekamilika. Kila kitu kimefutwa. Karibu tena wakati wowote.",
    },
}

# fewer lines on ussd screens because space is tight
ussd_crisis_lines = ["redcross"]
ussd_urgent_lines = ["redcross", "gbv", "child"]


def sms(key, lang, **kwargs):
    template = sms_copy[key][lang if lang in langs else "en"]
    return template.format(emergency=emergency_number(), **kwargs)


def ussd(key, lang):
    return ussd_copy[key][lang if lang in langs else "en"]


# the gsm 03.38 character set, including the extension characters that still count as gsm 7
gsm7_chars = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
    "^{}\\[~]|€"
)


def is_gsm7(text):
    return all(ch in gsm7_chars for ch in text)
