import logging
from typing import Protocol

import httpx

from app import db
from app.config import get_settings
from app.privacy import decrypt, mask_phone

log = logging.getLogger(__name__)

# outbound sms, through africa's talking in production and printed to the log everywhere else
# free for the user comes from the deal with the operators, not from code
# the sponsor contracts a zero rated shortcode and ussd code and pays for outbound sms


# anything that can send an sms
class sms_gateway(Protocol):
    async def send(self, to, message): ...


# keeps sent messages in memory for local runs and tests
class console_gateway:
    def __init__(self):
        self.sent = []

    async def send(self, to, message):
        self.sent.append((to, message))
        log.info("sms to %s %s", mask_phone(to), message)
        return True


class africas_talking_gateway:
    live_url = "https://api.africastalking.com/version1/messaging"
    sandbox_url = "https://api.sandbox.africastalking.com/version1/messaging"

    def __init__(self, username, api_key, sender_id=""):
        self.username = username
        self.api_key = api_key
        self.sender_id = sender_id
        self.url = self.sandbox_url if username == "sandbox" else self.live_url
        self._client = httpx.AsyncClient(timeout=15)

    async def send(self, to, message):
        # returns True only when africa's talking accepted the message for every recipient
        data = {"username": self.username, "to": to, "message": message}
        if self.sender_id:
            data["from"] = self.sender_id
        try:
            r = await self._client.post(
                self.url, data=data, headers={"apiKey": self.api_key, "Accept": "application/json"}
            )
            r.raise_for_status()
            recipients = r.json().get("SMSMessageData", {}).get("Recipients", [])
            ok = bool(recipients) and all(rec.get("status") == "Success" for rec in recipients)
            if not ok:
                log.error("africa's talking rejected sms to %s %s", mask_phone(to), recipients)
            return ok
        except httpx.HTTPError as e:
            log.error("africa's talking request failed for %s %s", mask_phone(to), e)
            return False


_gateway = None


def get_gateway():
    global _gateway
    if _gateway is None:
        s = get_settings()
        if s.sms_gateway == "africastalking":
            _gateway = africas_talking_gateway(s.at_username, s.at_api_key, s.at_sender_id)
        else:
            _gateway = console_gateway()
    return _gateway


def set_gateway(gateway):
    global _gateway
    _gateway = gateway


async def send_to_user(user_hash, message, channel="sms"):
    # the number is decrypted only at send time
    # a copy goes into the person's thread so counselors see the whole conversation
    user = db.get_user(user_hash)
    phone = decrypt(user["phone_enc"]) if user else None
    if not phone:
        return False
    ok = await get_gateway().send(phone, message)
    if ok:
        db.save_message(user_hash, "out", channel, message)
    return ok
