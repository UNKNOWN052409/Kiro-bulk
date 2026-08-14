"""
Mail Reader — Read emails from Gmail via IMAP (OAuth2)
=======================================================
Usage:
    python mail_reader.py              # Print all unread emails
    python mail_reader.py --test       # Test IMAP connection only
    python mail_reader.py --all        # Include already-read emails
    python mail_reader.py --folder INBOX  # Specify folder
    python mail_reader.py --count 5    # Limit to 5 emails
"""

import imaplib
import email
import email.header
import email.utils
import argparse
import logging
import sys
from datetime import datetime
from typing import List, Dict, Optional

from mail_config import (
    GMAIL_EMAIL, IMAP_HOST, IMAP_PORT,
    INBOX_FOLDER, MAX_EMAILS_PER_POLL, LOG_FILE
)

# Lazy import — gmail_oauth requires google-auth which may not be installed
get_imap_connection = None
try:
    from gmail_oauth import get_imap_connection  # OAuth2 XOAUTH2 auth
except ImportError:
    pass

# ── Logging setup ─────────────────────────────────────────────────────────────
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
        except (OSError, UnicodeEncodeError):
            try:
                msg = self.format(record)
                s = msg.encode('ascii', errors='replace').decode('ascii')
                self.stream.write(s + self.terminator)
                self.flush()
            except Exception:
                pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        SafeStreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


# Use app password IMAP connection (more reliable than OAuth2 in headless mode)
APP_PASSWORD = "hlcveobitfwhterw"

def connect_imap():
    """Connect to Gmail IMAP using app password."""
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(GMAIL_EMAIL, APP_PASSWORD)
    return conn


def test_connection() -> bool:
    """Test IMAP connection and return True if successful."""
    if connect_imap is None:
        log.error("❌ gmail_oauth not available (google-auth not installed)")
        return False
    try:
        conn = connect_imap()
        status, folders = conn.list()
        log.info(f"📂 Available folders:")
        for folder in folders:
            log.info(f"   {folder.decode()}")
        conn.logout()
        log.info("✅ Connection test PASSED")
        return True
    except Exception as e:
        log.error(f"❌ Connection test FAILED: {e}")
        return False


# ── Email Parsing ─────────────────────────────────────────────────────────────
def decode_header_value(value: str) -> str:
    """Decode encoded email header value (handles UTF-8, base64, etc.)"""
    if not value:
        return ""
    parts = email.header.decode_header(value)
    decoded = []
    for text, charset in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(text))
    return " ".join(decoded)


def extract_body(msg: email.message.Message) -> Dict[str, str]:
    """Extract plain text and HTML body from email."""
    body = {"text": "", "html": ""}

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition:
                continue

            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                body["text"] += payload.decode(charset, errors="replace")

            elif content_type == "text/html":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                body["html"] += payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        if payload:
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                body["html"] = text
            else:
                body["text"] = text

    return body


def extract_attachments(msg: email.message.Message) -> List[Dict]:
    """List all attachments in an email."""
    attachments = []
    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        if "attachment" in disposition:
            filename = part.get_filename()
            if filename:
                filename = decode_header_value(filename)
            attachments.append({
                "filename": filename or "unnamed",
                "content_type": part.get_content_type(),
                "size": len(part.get_payload(decode=True) or b"")
            })
    return attachments


def parse_email(raw_data: bytes, uid: str) -> Dict:
    """Parse raw email bytes into a structured dict."""
    msg = email.message_from_bytes(raw_data)
    body = extract_body(msg)
    attachments = extract_attachments(msg)

    # Parse date
    date_str = msg.get("Date", "")
    try:
        date_parsed = email.utils.parsedate_to_datetime(date_str)
    except Exception:
        date_parsed = None

    return {
        "uid":          uid,
        "message_id":   msg.get("Message-ID", ""),
        "from":         decode_header_value(msg.get("From", "")),
        "to":           decode_header_value(msg.get("To", "")),
        "cc":           decode_header_value(msg.get("Cc", "")),
        "subject":      decode_header_value(msg.get("Subject", "(no subject)")),
        "date":         date_parsed,
        "date_raw":     date_str,
        "body_text":    body["text"].strip(),
        "body_html":    body["html"].strip(),
        "attachments":  attachments,
        "is_read":      False,
    }


# ── Fetch Emails ──────────────────────────────────────────────────────────────
def fetch_emails(
    folder: str = INBOX_FOLDER,
    unread_only: bool = True,
    limit: int = MAX_EMAILS_PER_POLL,
    mark_as_read: bool = False,
    since_date: str = None
) -> List[Dict]:
    """
    Fetch emails from Gmail via IMAP (OAuth2).

    Args:
        folder:       IMAP folder name (e.g. 'INBOX')
        unread_only:  Only fetch unseen emails if True
        limit:        Max number of emails to return
        mark_as_read: Mark fetched emails as read

    Returns:
        List of parsed email dicts
    """
    emails = []

    if connect_imap is None:
        log.error("❌ gmail_oauth not available (google-auth not installed)")
        return []

    try:
        conn = connect_imap()
        conn.select(f'"{folder}"')

        # Search criteria — IMAP SINCE uses dd-Mon-yyyy format
        if since_date:
            criteria = f'(SINCE {since_date})'
            if unread_only:
                criteria = f'(SINCE {since_date} UNSEEN)'
        elif unread_only:
            criteria = "UNSEEN"
        else:
            criteria = "ALL"
        status, data = conn.uid("search", None, criteria)

        if status != "OK" or not data[0]:
            log.info(f"📭 No {'unread ' if unread_only else ''}emails in {folder}")
            conn.logout()
            return []

        uids = data[0].split()
        log.info(f"📬 Found {len(uids)} {'unread ' if unread_only else ''}email(s) in {folder}")

        # Fetch most recent first (reverse order), up to limit
        uids_to_fetch = uids[-limit:][::-1]

        for uid in uids_to_fetch:
            status, msg_data = conn.uid("fetch", uid, "(RFC822)")
            if status == "OK" and msg_data[0]:
                raw = msg_data[0][1]
                try:
                    parsed = parse_email(raw, uid.decode())
                    emails.append(parsed)
                    log.info(f"   📧 [{uid.decode()}] From: {parsed['from'][:40]} | Subject: {parsed['subject'][:50]}")
                except Exception as e:
                    log.warning(f"   ⚠️  [{uid.decode()}] Skipping email due to parse error: {e}")
                    continue

                if mark_as_read:
                    conn.uid("store", uid, "+FLAGS", r"\Seen")

        conn.logout()

    except Exception as e:
        log.error(f"❌ Error fetching emails: {e}")
        raise

    return emails


def mark_email_read(uid: str, folder: str = INBOX_FOLDER) -> bool:
    """Mark a specific email as read by UID."""
    try:
        conn = connect_imap()
        conn.select(f'"{folder}"')
        conn.uid("store", uid.encode(), "+FLAGS", r"\Seen")
        conn.logout()
        log.info(f"✅ Marked email {uid} as read")
        return True
    except Exception as e:
        log.error(f"❌ Failed to mark email {uid} as read: {e}")
        return False


def print_email_summary(emails: List[Dict]):
    """Pretty-print a list of emails to console."""
    if not emails:
        print("\n📭 No emails to display.\n")
        return

    print(f"\n{'═' * 70}")
    print(f"  📬 {len(emails)} Email(s)")
    print(f"{'═' * 70}")

    for i, mail in enumerate(emails, 1):
        date_str = mail["date"].strftime("%Y-%m-%d %H:%M") if mail["date"] else mail["date_raw"]
        print(f"\n  ── Email #{i} (UID: {mail['uid']}) ──")
        print(f"  From   : {mail['from']}")
        print(f"  To     : {mail['to']}")
        print(f"  Subject: {mail['subject']}")
        print(f"  Date   : {date_str}")
        if mail["attachments"]:
            print(f"  Files  : {', '.join(a['filename'] for a in mail['attachments'])}")
        print(f"  Body   :")
        body_preview = (mail["body_text"] or "[HTML only]")[:300]
        for line in body_preview.split("\n")[:8]:
            print(f"    {line}")
        if len(mail["body_text"]) > 300:
            print("    ... (truncated)")

    print(f"\n{'═' * 70}\n")


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read emails from Gmail via IMAP")
    parser.add_argument("--test",   action="store_true", help="Test IMAP connection only")
    parser.add_argument("--all",    action="store_true", help="Fetch all emails (not just unread)")
    parser.add_argument("--folder", default=INBOX_FOLDER, help="IMAP folder to read")
    parser.add_argument("--count",  type=int, default=MAX_EMAILS_PER_POLL, help="Max emails to fetch")
    parser.add_argument("--mark-read", action="store_true", help="Mark fetched emails as read")
    args = parser.parse_args()

    if args.test:
        success = test_connection()
        sys.exit(0 if success else 1)

    emails = fetch_emails(
        folder=args.folder,
        unread_only=not args.all,
        limit=args.count,
        mark_as_read=args.mark_read
    )
    print_email_summary(emails)

