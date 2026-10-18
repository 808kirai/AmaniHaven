AmaniHaven

Free, confidential mental health support for anyone with a basic phone. People dial a USSD code or send an SMS. AmaniHaven replies straight away with grounding exercises and self-help in English or Kiswahili, and alerts a human counselor within seconds when someone is at risk.

How it breaks the four barriers

- No smartphone or internet - Everything runs over USSD menus and SMS, so it works on any 2G feature phone with no app and no data bundle.
- Cost - It is built for a zero rated USSD code and a toll-free shortcode, with the sponsor paying for outbound SMS. All copy uses GSM-7 characters and stays within tested SMS segment budgets, so each reply costs as little as possible. See Making it free below.
- Too few professionals - Most messages get an instant, reviewed self-help reply with no human needed. Counselors are paged only for crisis or abuse, or when someone asks for a call, and each person gets one case card however many messages they send.
- Stigma and privacy - Nobody has to walk into a clinic. Phone numbers are stored only as a keyed hash plus an encrypted copy. Messages are encrypted and deleted after 30 days, and people can erase everything by texting DELETE or FUTA. Counselor alerts never contain the person's words or number.

What changed from the original concept

Anonymous became confidential. The mobile network always sees the number, and so must we in order to reply. We can honestly promise confidentiality and minimal data, so that is what the product says.

The AI never talks to users. Claude classifies risk, and every word a user sees comes from `app/content.py`, which a clinician and a translator can review in one sitting.

The AI can only raise risk, never lower it. Offline rules run first and always. Claude can escalate a message but cannot downgrade one, so when Claude is slow, down or switched off, or gets a message saying mark this routine, the rules still hold.

Unclear messages get a direct question. Messages like "I'm not suicidal" or "tired of living" lead to "are you having thoughts of ending your life? YES/NO". Asking directly is standard clinical practice and does not raise risk. A YES opens a crisis case.

There is a self-check. The USSD menu offers the PHQ-4, two anxiety and two depression questions, plus a safety question, with results and next steps on screen.

Kiswahili throughout. Replies come back in the language the person writes in, and they can switch with SW or EN.

Counselor tooling. A dashboard shows the thread and lets counselors reply by SMS, claim and close cases, and reveal a number for a call. Revealing a number is logged and needs consent or a crisis case.

Consent before contact. A USSD screen never triggers an unexpected SMS or call. Someone who answers YES to the safety question is shown the numbers and offered a call, because an unexpected SMS on a shared phone can expose them.

Run it

Tested on Python 3.12.

```bash
pip install -r requirements.txt

# run the tests
python -m pytest -q

# dial the menu or text the line from your terminal
python -m scripts.simulate ussd
python -m scripts.simulate sms
```

To run the server, copy `.env.example` to `.env`, fill it in, then start it.

```bash
uvicorn app.main:app --reload
```

The counselor dashboard is at http://localhost:8000/counselor and takes a token from `COUNSELOR_TOKENS`. With `LLM_ENABLED=false` it runs on the rules alone and needs no Claude API key.

Connecting Africa's Talking

Start in the Africa's Talking sandbox and set these callback URLs in their dashboard.

- USSD - `https://YOUR_HOST/ussd?key=WEBHOOK_SECRET`
- Incoming SMS - `https://YOUR_HOST/sms/inbound?key=WEBHOOK_SECRET`
- SMS delivery reports - `https://YOUR_HOST/sms/delivery?key=WEBHOOK_SECRET`

Then set `SMS_GATEWAY=africastalking`, `AT_USERNAME`, `AT_API_KEY` and `AT_SENDER_ID`. Africa's Talking does not sign its callbacks, so also allow only their IP ranges at your load balancer.

Making it free

The code keeps costs low, but free for the user comes from the deal with the operators.

- USSD - Ask Africa's Talking for a zero rated USSD code, where the session is billed to you and not to the person dialling.
- Incoming SMS - Use a toll-free shortcode. A standard shortcode charges the sender.
- Outbound SMS - You pay per segment. Tests hold menus and confirmations to one segment, support replies to two and crisis replies to three. `MAX_REPLIES_PER_HOUR` limits abuse, but crisis replies are never limited.
- Triage - One low effort Claude call per free text SMS, skipped when the rules have already found a crisis.

Confirm current prices and zero rating with Africa's Talking and each operator, Safaricom, Airtel and Telkom.

How it works

```
feature phone --USSD--> /ussd --> ussd.py, a menu that replays the keypress path
              --SMS---> /sms/inbound --> sms.py
                                          answers to our yes or no questions
                                          keywords like HELP, CALL and DELETE
                                          triage, offline rules then Claude, which can only raise risk
                                       --> reply from content.py
                                       --> counselor alert with no message content
counselor --> /counselor dashboard --> /api/counselor, every action logged
```

Each message lands in one of four tiers.

- crisis - Suicidal intent, self-harm, overdose, or YES to the safety question. The person gets helplines, a case opens and counselors are paged.
- safeguarding - Abuse, rape, violence or threats. The person gets the GBV and Childline numbers, a case opens and counselors are paged.
- elevated - Hopelessness, panic or not coping. The person gets a supportive reply, a tip and the offer of a call. Three such messages in a day open a case without paging anyone.
- routine - Everyday stress, questions and greetings. The person gets a self-help tip matched to their topic.

Layout

- `app/content.py` - Every word users see, the file to send to clinical and translation reviewers
- `app/triage/rules.py` - English, Kiswahili and Sheng risk word list
- `app/triage/llm.py` - Claude classifier with structured output and a safe fallback
- `app/triage/engine.py` - Combines the two verdicts
- `app/ussd.py` - USSD menu, PHQ-4 check-in and exercises
- `app/sms.py` - SMS conversation flow
- `app/counselor.py` - Counselor API
- `app/static/counselor.html` - Counselor dashboard
- `app/privacy.py` - Hashing, encryption and number masking
- `app/db.py` - Storage, retention purge and right to erasure
- `app/gateway.py` - Africa's Talking SMS sending
- `scripts/simulate.py` - Try the service from a terminal
- `tests/` - Automated tests

Settings

All settings come from environment variables, listed with examples in `.env.example`.

- `APP_ENV` - Set to production to refuse starting without the required secrets
- `PHONE_HASH_PEPPER` and `DATA_ENCRYPTION_KEY` - Privacy keys, generate once and back up
- `RETENTION_DAYS` - Days before messages are deleted, defaults to `30`
- `SMS_GATEWAY` - `console` prints messages, `africastalking` sends them
- `LLM_ENABLED` - Turns the Claude second opinion on or off
- `COUNSELOR_TOKENS` - Counselor names and dashboard tokens
- `COUNSELOR_ALERT_NUMBERS` - Phones paged for crisis cases
- `MAX_REPLIES_PER_HOUR` - Reply limit per person, defaults to `20`

Before launch

These are not optional for a crisis service.

- Call every helpline number in `default_helplines` in `app/config.py` and confirm it is current, free where we say free, and staffed when we say so.
- Have a licensed mental health professional review `app/content.py` and the word lists in `app/triage/rules.py`.
- Have a native speaker review all Kiswahili copy and add Sheng to the word list.
- Staff an on-call rota that matches the crisis SMS promise that a counselor will text back as soon as possible. If nobody is on call at night, change that sentence for those hours.
- Write the escalation protocol for imminent risk, including when to involve emergency services and the duty of care policy for revealing a number in a crisis case without consent.
- Under the Kenya Data Protection Act 2019, register with the ODPC, complete a DPIA since health data is sensitive personal data, and settle the legal basis for sending message text to the Claude API outside Kenya. Get legal advice.
- Decide how under-18s are handled, including Childline referral and consent.
- Generate `PHONE_HASH_PEPPER` and `DATA_ENCRYPTION_KEY` once, store them in a secrets manager and back them up.
- In production, use HTTPS, the Africa's Talking IP allow list and encrypted backups, and move from SQLite to Postgres once traffic grows.
- Measure triage on a labelled set of real, consented and anonymised messages before trusting it, and track missed crises above everything else.

Ideas for later

- An opt-in daily check-in SMS with trend alerts
- A voice line for people who cannot read
- More languages such as Dholuo, Kikuyu and Somali, plus Sheng copy
- Peer support groups over SMS, moderated by counselors
- A sponsor dashboard built on `/api/admin/stats`, with anonymous totals only

Licence

All rights reserved. Nobody may use, copy, change or share this code without written permission. See `LICENSE`.
