"""
Havenhaus.in Custom Domain Mail Provider
=========================================
Uses @havenhaus.in domain for account creation.
OTP retrieval via Gmail IMAP (anshika31618@gmail.com with app password).

The havenhaus.in domain has MX records configured to forward
all emails (@havenhaus.in) to the Gmail inbox.
We poll the Gmail IMAP account for OTP messages addressed to
the created havenhaus.in alias.

Usage:
    provider = HavenhausProvider(
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_user="anshika31618@gmail.com",
        imap_pass="kaya abts edky xdpf",
        domains=["havenhaus.in"]
    )
    email = provider.create_mailbox()  # e.g., "abc123def4@havenhaus.in"
    otp = provider.wait_otp(timeout=180)  # Returns 6-digit code
"""
from __future__ import annotations

import email
import email.message
import email.utils
import imaplib
import random
import re
import string
import time
from email.header import decode_header

from .base import MailProvider


def _random_local(length: int = 10) -> str:
    """Generate a random local part for the email address."""
    pool = string.ascii_lowercase + string.digits
    return "".join(random.choices(pool, k=length))


def _decode_header_value(raw: str) -> str:
    """Best-effort decode of a MIME-encoded email header."""
    if not raw:
        return ""
    parts = []
    for chunk, enc in decode_header(raw):
        if isinstance(chunk, bytes):
            try:
                parts.append(chunk.decode(enc or "utf-8", errors="ignore"))
            except LookupError:
                parts.append(chunk.decode("utf-8", errors="ignore"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _extract_bodies(msg: email.message.Message) -> list[str]:
    """Return every text/* part body as a list of decoded strings."""
    out: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype.startswith("text/"):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        out.append(payload.decode(charset, errors="ignore"))
                    except LookupError:
                        out.append(payload.decode("utf-8", errors="ignore"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                out.append(payload.decode(charset, errors="ignore"))
            except LookupError:
                out.append(payload.decode("utf-8", errors="ignore"))
        elif msg.get_payload():
            out.append(str(msg.get_payload()))
    return out


class HavenhausProvider(MailProvider):
    """
    Custom domain provider for @havenhaus.in.
    Uses Gmail IMAP to poll for OTP messages.
    """
    name = "havenhaus"
    display_name = "Havenhaus.in (Gmail IMAP)"

    def __init__(
        self,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        imap_user: str = "",
        imap_pass: str = "",
        imap_folder: str = "INBOX",
        domains: list[str] | None = None,
        local_prefix: str = "",
        local_length: int = 10,
    ):
        self.imap_host = imap_host
        self.imap_port = int(imap_port) if imap_port else 993
        self.imap_user = imap_user
        self.imap_pass = imap_pass
        self.imap_folder = imap_folder or "INBOX"
        self.local_prefix = local_prefix or ""
        self.local_length = max(4, int(local_length))

        # Default domain pool
        if domains:
            self.domains = [d.strip().lower() for d in domains if d and d.strip()]
        else:
            self.domains = ["havenhaus.in"]

        # Per-mailbox state
        self.address: str | None = None
        self._created_at: float = 0.0
        self._seen_uids: set[str] = set()

    def create_mailbox(self) -> str:
        """Create a random @havenhaus.in email address."""
        domain = random.choice(self.domains)
        local = f"{self.local_prefix}{_random_local(self.local_length)}"
        self.address = f"{local}@{domain}"
        self._created_at = time.time()
        self._seen_uids = set()
        return self.address

    def wait_otp(self, timeout: int = 120, poll_interval: int = 3) -> str:
        """Poll Gmail IMAP for OTP code sent to the created address."""
        if not self.address:
            raise RuntimeError("Call create_mailbox() before wait_otp().")
        if not self.imap_user or not self.imap_pass:
            raise RuntimeError("IMAP credentials missing (imap_user / imap_pass).")

        deadline = time.time() + max(timeout, 1)
        target = self.address.lower()

        while time.time() < deadline:
            try:
                code = self._poll_once(target)
                if code:
                    return code
            except imaplib.IMAP4.error:
                # Transient IMAP error — reconnect on next loop
                pass
            except Exception:
                # Don't let exotic errors kill the polling loop
                pass
            time.sleep(max(1, int(poll_interval)))

        return ""

    def list_domains(self) -> list[dict]:
        """Return available domains."""
        return [{"id": d, "domain": d} for d in self.domains]

    # ── Internal IMAP methods ──

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Connect and login to Gmail IMAP."""
        imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        imap.login(self.imap_user, self.imap_pass)
        imap.select(self.imap_folder, readonly=False)
        return imap

    def _poll_once(self, target_address: str) -> str:
        """Single IMAP poll iteration. Returns the 6-digit OTP or empty string."""
        imap = self._connect()
        try:
            # Search for messages sent to our target address since mailbox creation
            since_date = time.strftime(
                "%d-%b-%Y", time.gmtime(max(self._created_at - 86400, 0))
            )
            uids: list[str] = []
            
            # Try compound query first
            status, data = imap.uid(
                "SEARCH", None, f'(SINCE "{since_date}" TO "{target_address}")'
            )
            if status == "OK" and data and data[0]:
                uids = data[0].decode(errors="ignore").split()

            # Fallback: some IMAP servers dislike the compound query
            if not uids:
                status, data = imap.uid("SEARCH", None, f'(TO "{target_address}")')
                if status == "OK" and data and data[0]:
                    uids = data[0].decode(errors="ignore").split()
            
            # Additional fallback: search by subject keywords (AWS/verify)
            if not uids:
                for kw in ["AWS", "verify", "verification", "Builder ID", "Amazon"]:
                    status, data = imap.uid("SEARCH", None, f'(SINCE "{since_date}" SUBJECT "{kw}")')
                    if status == "OK" and data and data[0]:
                        for u in data[0].decode(errors="ignore").split():
                            if u not in uids:
                                uids.append(u)

            # Also fetch only recent unread messages as a catch-all (limit to last 50)
            status, data = imap.uid("SEARCH", None, "UNSEEN")
            if status == "OK" and data and data[0]:
                all_unseen = data[0].decode(errors="ignore").split()
                # Only take the last 50 (most recent)
                recent_unseen = all_unseen[-50:]
                for u in recent_unseen:
                    if u not in uids:
                        uids.append(u)

            # Scan newest first
            for uid in reversed(uids):
                if uid in self._seen_uids:
                    continue
                self._seen_uids.add(uid)

                status, msg_data = imap.uid("FETCH", uid, "(BODY.PEEK[])")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else None
                if not raw:
                    continue

                msg = email.message_from_bytes(raw)

                # Check To/Delivered-To headers
                to_haystack = " ".join(
                    _decode_header_value(msg.get(h, ""))
                    for h in ("To", "Delivered-To", "X-Original-To",
                              "X-Forwarded-To", "X-Delivered-To")
                ).lower()
                
                # Accept if target address is in To headers OR if subject/body contains AWS keywords
                is_target = target_address in to_haystack
                subject = _decode_header_value(msg.get("Subject", ""))
                all_bodies = _extract_bodies(msg)
                body_text = " ".join(all_bodies).lower()
                is_aws = any(kw in subject.lower() or kw in body_text for kw in 
                           ["aws", "verify", "verification", "builder id", "amazon", "code"])
                
                if not is_target and not is_aws:
                    continue

                # Timestamp filter
                ts = self._message_epoch(msg)
                if ts and ts + 5 < self._created_at:
                    continue

                # Try subject first
                m = re.search(r"\b(\d{6})\b", subject)
                if m:
                    return m.group(1)

                # Try body
                for body in all_bodies:
                    m = re.search(r"\b(\d{6})\b", body)
                    if m:
                        return m.group(1)

        finally:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass

        return ""

    @staticmethod
    def _message_epoch(msg: email.message.Message) -> float:
        """Extract epoch timestamp from message Date header."""
        date_hdr = msg.get("Date") or msg.get("Received", "")
        try:
            tup = email.utils.parsedate_tz(date_hdr)
            if tup:
                return email.utils.mktime_tz(tup)
        except Exception:
            pass
        return 0.0
