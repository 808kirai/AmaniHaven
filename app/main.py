import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Form, Header, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

from app import db
from app.config import get_settings
from app.counselor import router as counselor_router
from app.sms import handle_inbound_sms
from app.ussd import handle_ussd

# web entry points
# /ussd and /sms/inbound take africa's talking callbacks, /sms/delivery takes delivery reports
# /counselor is the dashboard, /api/counselor its api and /api/admin/stats gives sponsors anonymous numbers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("amanihaven")

static_dir = Path(__file__).parent / "static"


async def _purge_loop():
    # clears data past the retention window every six hours
    while True:
        try:
            n = db.purge_expired(get_settings().retention_days)
            if n:
                log.info("retention purge removed %d messages", n)
        except Exception:
            log.exception("retention purge failed")
        await asyncio.sleep(6 * 3600)


@asynccontextmanager
async def lifespan(app):
    # loading settings here makes production fail fast when a secret is missing
    get_settings()
    task = asyncio.create_task(_purge_loop())
    yield
    task.cancel()


app = FastAPI(title="AmaniHaven", lifespan=lifespan)
app.include_router(counselor_router)


def verify_webhook(key: str = Query(default="")):
    # africa's talking doesn't sign callbacks, so the callback urls carry a secret key
    # also allow list their ip ranges at the load balancer
    secret = get_settings().webhook_secret
    if secret and not hmac.compare_digest(key, secret):
        raise HTTPException(status_code=403)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ussd", response_class=PlainTextResponse, dependencies=[Depends(verify_webhook)])
async def ussd(
    background: BackgroundTasks,
    sessionId: str = Form(...),
    phoneNumber: str = Form(...),
    text: str = Form(default=""),
    serviceCode: str = Form(default=""),
):
    result = handle_ussd(phoneNumber, text)
    for followup in result.followups:
        background.add_task(followup)
    return result.body


async def _safe_handle_sms(phone, text):
    # one bad message must not stop the worker, and the log never holds message text
    try:
        await handle_inbound_sms(phone, text)
    except Exception:
        log.exception("failed to handle inbound sms")


@app.post("/sms/inbound", dependencies=[Depends(verify_webhook)])
async def sms_inbound(
    background: BackgroundTasks,
    from_: str = Form(..., alias="from"),
    text: str = Form(default=""),
    to: str = Form(default=""),
    id: str = Form(default=""),
):
    # answer straight away, triage can take a few seconds and africa's talking retries slow callbacks
    background.add_task(_safe_handle_sms, from_, text)
    return {"ok": True}


@app.post("/sms/delivery", dependencies=[Depends(verify_webhook)])
async def sms_delivery(id: str = Form(default=""), status: str = Form(default=""), failureReason: str = Form(default="")):
    if status not in ("Success", "Sent", "Buffered", "Submitted"):
        log.warning("sms %s delivery status %s %s", id, status, failureReason)
        db.record_event("sms_delivery_failed", channel="sms")
    return {"ok": True}


@app.get("/counselor", include_in_schema=False)
def counselor_dashboard():
    return FileResponse(static_dir / "counselor.html")


def require_admin(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    admin = get_settings().admin_token
    if not admin or not hmac.compare_digest(token, admin):
        raise HTTPException(status_code=401)


@app.get("/api/admin/stats", dependencies=[Depends(require_admin)])
def admin_stats(days: int = 30):
    return db.stats(days)
