import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app import content, db
from app.config import get_settings
from app.gateway import send_to_user
from app.privacy import decrypt, encrypt, mask_phone

# the api behind the counselor dashboard
# every action goes in the audit log and numbers stay masked unless a counselor chooses to reveal one

router = APIRouter(prefix="/api/counselor", tags=["counselor"])


def current_counselor(authorization: str = Header(default="")):
    # returns the counselor's name for a valid token
    token = authorization.removeprefix("Bearer ").strip()
    for known, name in get_settings().counselor_tokens.items():
        if token and hmac.compare_digest(token, known):
            return name
    raise HTTPException(status_code=401, detail="Invalid counselor token")


def _case_or_404(case_id):
    case = db.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _case_view(case):
    # everything the dashboard shows for one case, with the thread decrypted
    user = db.get_user(case["user_hash"])
    thread = [
        {"direction": m["direction"], "text": decrypt(m["body_enc"]), "tier": m["tier"], "at": m["created_at"]}
        for m in db.recent_messages(case["user_hash"], 20)
    ]
    return {
        "id": case["id"],
        "tier": case["tier"],
        "status": case["status"],
        "source": case["source"],
        "reason": case["reason"],
        "claimed_by": case["claimed_by"],
        "created_at": case["created_at"],
        "updated_at": case["updated_at"],
        "note": decrypt(case["note_enc"]),
        "language": user["language"] if user else None,
        "callback_consent": bool(user and user["callback_consent"]),
        "opted_out": bool(user and user["opted_out"]),
        "phone_masked": mask_phone(decrypt(user["phone_enc"])) if user else None,
        "thread": thread,
    }


@router.get("/me")
def me(counselor: str = Depends(current_counselor)):
    return {"name": counselor}


@router.get("/cases")
def list_cases(status: str | None = None, counselor: str = Depends(current_counselor)):
    return [_case_view(c) for c in db.list_cases(status)]


@router.post("/cases/{case_id}/claim")
def claim(case_id: int, counselor: str = Depends(current_counselor)):
    case = _case_or_404(case_id)
    if case["status"] == "claimed" and case["claimed_by"] != counselor:
        raise HTTPException(status_code=409, detail=f"Already claimed by {case['claimed_by']}")
    db.update_case(case_id, status="claimed", claimed_by=counselor)
    db.audit(counselor, "claim", case_id)
    return _case_view(db.get_case(case_id))


# up to three sms segments
class reply_body(BaseModel):
    text: str = Field(min_length=1, max_length=459)


@router.post("/cases/{case_id}/reply")
async def reply(case_id: int, body: reply_body, counselor: str = Depends(current_counselor)):
    case = _case_or_404(case_id)
    user = db.get_user(case["user_hash"])
    if user is None:
        raise HTTPException(status_code=410, detail="This person deleted their data")
    if user["opted_out"]:
        raise HTTPException(status_code=409, detail="This person texted STOP; wait for them to write again")
    message = content.sms("counselor_prefix", user["language"]) + body.text
    if not await send_to_user(case["user_hash"], message):
        raise HTTPException(status_code=502, detail="SMS gateway did not accept the message")
    if case["status"] == "open":
        db.update_case(case_id, status="claimed", claimed_by=counselor)
    db.audit(counselor, "reply", case_id)
    return _case_view(db.get_case(case_id))


@router.post("/cases/{case_id}/reveal-phone")
def reveal_phone(case_id: int, counselor: str = Depends(current_counselor)):
    # the full number for a phone call
    # allowed when the person asked for a call, or for crisis cases under the duty of care policy
    case = _case_or_404(case_id)
    user = db.get_user(case["user_hash"])
    if user is None:
        raise HTTPException(status_code=410, detail="This person deleted their data")
    if not user["callback_consent"] and case["tier"] != "crisis":
        raise HTTPException(status_code=403, detail="No call-back consent for this case")
    db.audit(counselor, "reveal_phone", case_id)
    return {"phone": decrypt(user["phone_enc"])}


class close_body(BaseModel):
    note: str = Field(default="", max_length=2000)


@router.post("/cases/{case_id}/close")
def close(case_id: int, body: close_body, counselor: str = Depends(current_counselor)):
    _case_or_404(case_id)
    db.update_case(case_id, status="closed", note_enc=encrypt(body.note) if body.note else None)
    db.audit(counselor, "close", case_id)
    return {"ok": True}
