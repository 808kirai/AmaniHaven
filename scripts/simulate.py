import asyncio
import os
import sys
import tempfile

# try amanihaven from a terminal the way a feature phone would, with no telecom setup
# python -m scripts.simulate ussd dials the menu
# python -m scripts.simulate sms texts the line
# replies and counselor alerts print as they would arrive
# uses a throwaway database unless DATABASE_PATH is set

os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "amanihaven-sim.db"))
os.environ.setdefault("SMS_GATEWAY", "console")
os.environ.setdefault("COUNSELOR_ALERT_NUMBERS", "+254700000000")

from app.gateway import set_gateway  # noqa: E402
from app.sms import handle_inbound_sms  # noqa: E402
from app.ussd import handle_ussd  # noqa: E402

phone = os.getenv("SIM_PHONE", "+254712000000")


# prints each sms instead of sending it
class printing_gateway:
    async def send(self, to, message):
        who = "COUNSELOR ALERT" if to != phone else "SMS"
        print(f"\n  [{who}] {message}\n")
        return True


def ussd():
    path = []
    print("Dialling... (type q to hang up)\n")
    while True:
        result = handle_ussd(phone, "*".join(path))
        for f in result.followups:
            asyncio.run(f())
        print("+" + "-" * 34 + "+")
        print(result.text)
        print("+" + "-" * 34 + "+")
        if result.end:
            path = []
            if input("\nSession ended. Dial again? [y/n] ").strip().lower() != "y":
                return
            continue
        key = input("> ").strip()
        if key.lower() == "q":
            return
        path.append(key)


def sms():
    print("Text AmaniHaven (type q to quit). Try: 'hello', 'nimechoka sana', 'MENU', 'HELP'.\n")
    while True:
        text = input("you> ").strip()
        if text.lower() == "q":
            return
        asyncio.run(handle_inbound_sms(phone, text))


if __name__ == "__main__":
    set_gateway(printing_gateway())
    mode = sys.argv[1] if len(sys.argv) > 1 else "ussd"
    {"ussd": ussd, "sms": sms}.get(mode, ussd)()
