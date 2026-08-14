"""Gmail OAuth mail provider for kiro-register-en.

Subclasses MailProvider. create_mailbox() returns a random @havenhaus.in
address (catch-all forwarded to the Gmail inbox readable via mail_reader OAuth).
wait_otp() polls that inbox for the AWS 6-digit code.
"""
import re
import sys
import time
from pathlib import Path

_BOT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated\automation\automation")
sys.path.insert(0, str(_BOT))

from mail_providers.base import MailProvider


class GmailOAuthProvider(MailProvider):
    name = "gmail_oauth"
    display_name = "Gmail OAuth (@havenhaus.in catch-all)"

    def __init__(self, domain="havenhaus.in", length=10):
        self.domain = domain
        self.length = length
        self.address = None
        self._seen = set()
        self._created_at = time.time()

    def create_mailbox(self) -> str:
        import random, string
        local = "".join(random.choices(string.ascii_lowercase + string.digits, k=self.length))
        self.address = f"{local}@{self.domain}"
        self._created_at = time.time()
        self._seen = set()
        return self.address

    def list_domains(self) -> list[dict]:
        return [{"id": self.domain, "domain": self.domain}]

    def wait_otp(self, timeout: int = 180, poll_interval: int = 4) -> str:
        if not self.address:
            raise RuntimeError("call create_mailbox() first")
        from mail_reader import fetch_emails
        target = self.address.lower()
        deadline = time.time() + max(timeout, 1)
        while time.time() < deadline:
            try:
                mails = fetch_emails(unread_only=True, limit=15, mark_as_read=False)
                for m in mails:
                    if m["uid"] in self._seen:
                        continue
                    self._seen.add(m["uid"])
                    to = (m.get("to") or "").lower()
                    subj = (m.get("subject") or "").lower()
                    body = (m.get("body_text") or m.get("body_html") or "")
                    if target in to and ("aws" in subj or "verify" in subj or "code" in subj or "otp" in subj):
                        mm = re.search(r"\b(\d{6})\b", body)
                        if mm:
                            return mm.group(1)
                    if target in to and re.search(r"\b\d{6}\b", body):
                        return re.search(r"\b(\d{6})\b", body).group(1)
            except Exception:
                pass
            time.sleep(max(1, int(poll_interval)))
        return ""
