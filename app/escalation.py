import logging

from app import db
from app.config import get_settings
from app.gateway import get_gateway

log = logging.getLogger(__name__)

# hands cases to the human team
# alerts carry only a case number and tier, never the person's words or number, because counselors' phones get seen too

# tiers that page the on call counselors straight away
alert_tiers = {"crisis", "safeguarding"}


async def escalate(user_hash, tier, source, reason, callback=False):
    case_id, needs_alert = db.open_case(user_hash, tier, source, reason)
    if needs_alert and (tier in alert_tiers or callback):
        label = "CALLBACK REQUEST" if callback and tier not in alert_tiers else tier.upper()
        text = f"AmaniHaven: {label} case #{case_id} needs a counselor. Open the dashboard."
        numbers = get_settings().counselor_alert_numbers
        for number in numbers:
            await get_gateway().send(number, text)
        if not numbers:
            log.warning("case %s opened as %s but COUNSELOR_ALERT_NUMBERS is empty", case_id, tier)
    return case_id
