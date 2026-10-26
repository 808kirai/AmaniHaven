import re
import secrets
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app import db
from app.config import get_settings
from app.counselor import _case_view, reply as counselor_reply, reply_body
from app.gateway import get_gateway, set_gateway
from app.privacy import hash_phone
from app.sms import handle_inbound_sms
from app.ussd import handle_ussd

# the public demo, a pretend phone that runs through the real menu, triage and case flow
# each visitor gets a made up number, and sms to those numbers stay on the page instead of being sent
# it only runs when DEMO_ENABLED is true, and config only allows that with the africa's talking sandbox

max_sessions = 300
max_actions_per_session = 150
demo_counselor = "Demo counselor"

router = APIRouter(prefix="/api/demo", tags=["demo"])


class demo_store:
    def __init__(self):
        # session id to phone, oldest first so the oldest can be dropped
        self.sessions = OrderedDict()
        # phone to the messages shown on that pretend phone
        self.threads = {}
        self.actions = {}
        # case ids whose alert went out to the on call counselors
        self.paged = set()


store = demo_store()


class demo_gateway:
    # keeps sms to demo numbers for the page and passes everything else to the real gateway
    def __init__(self, inner):
        self.inner = inner

    async def send(self, to, message):
        if to in store.threads:
            store.threads[to].append({"direction": "out", "text": message, "at": db.now()})
            return True
        found = re.search(r"case #(\d+)", message)
        if found:
            store.paged.add(int(found.group(1)))
        return await self.inner.send(to, message)


def _install():
    # wraps whatever gateway is current, tests swap gateways so this is checked on every call
    gateway = get_gateway()
    if not isinstance(gateway, demo_gateway):
        set_gateway(demo_gateway(gateway))


def enabled():
    if not get_settings().demo_enabled:
        raise HTTPException(status_code=404)


def _new_phone():
    while True:
        phone = "+254799" + "".join(secrets.choice("0123456789") for _ in range(6))
        if phone not in store.threads:
            return phone


def _drop_oldest():
    # forget the oldest visitor and wipe what the service stored about them
    sid, phone = store.sessions.popitem(last=False)
    store.threads.pop(phone, None)
    store.actions.pop(sid, None)
    db.delete_user_data(hash_phone(phone))


def _use(sid):
    # the phone for a session, counting each action against the session's limit
    phone = store.sessions.get(sid)
    if phone is None:
        raise HTTPException(status_code=404, detail="This demo has expired. Refresh the page to start again.")
    store.actions[sid] = store.actions.get(sid, 0) + 1
    if store.actions[sid] > max_actions_per_session:
        raise HTTPException(status_code=429, detail="That's the limit for one demo. Refresh the page to start again.")
    _install()
    return phone


def _state(phone):
    case = db.latest_case(hash_phone(phone))
    view = None
    if case:
        view = _case_view(case)
        view["paged"] = case["id"] in store.paged
    return {"messages": store.threads.get(phone, []), "case": view}


class text_body(BaseModel):
    id: str = Field(max_length=64)
    text: str = Field(default="", max_length=300)


@router.post("/start", dependencies=[Depends(enabled)])
def start():
    _install()
    sid, phone = secrets.token_urlsafe(16), _new_phone()
    store.sessions[sid] = phone
    store.threads[phone] = []
    while len(store.sessions) > max_sessions:
        _drop_oldest()
    s = get_settings()
    return {"id": sid, "ussd_code": s.ussd_code, "shortcode": s.sms_shortcode}


@router.get("/state", dependencies=[Depends(enabled)])
def state(id: str = Query(max_length=64)):
    phone = store.sessions.get(id)
    if phone is None:
        raise HTTPException(status_code=404, detail="This demo has expired. Refresh the page to start again.")
    return _state(phone)


@router.post("/ussd", dependencies=[Depends(enabled)])
async def ussd(body: text_body):
    # text is the whole keypress path joined with *, the way africa's talking sends it
    phone = _use(body.id)
    result = handle_ussd(phone, body.text)
    for followup in result.followups:
        await followup()
    return {"text": result.text, "end": result.end}


@router.post("/sms", dependencies=[Depends(enabled)])
async def sms(body: text_body):
    phone = _use(body.id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Write a message first.")
    store.threads[phone].append({"direction": "in", "text": text, "at": db.now()})
    await handle_inbound_sms(phone, text)
    return _state(phone)


@router.post("/reply", dependencies=[Depends(enabled)])
async def reply(body: text_body):
    # the visitor plays the counselor too, replying to their own case
    phone = _use(body.id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Write a reply first.")
    case = db.latest_case(hash_phone(phone))
    if case is None or case["status"] == "closed":
        raise HTTPException(status_code=409, detail="There's no open case to reply to yet.")
    await counselor_reply(case["id"], reply_body(text=text), counselor=demo_counselor)
    return _state(phone)
