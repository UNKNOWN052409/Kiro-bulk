"""
Mail Sender — Send emails via Gmail SMTP (OAuth2)
==================================================
Usage:
    python mail_sender.py --test                          # Test SMTP connection
    python mail_sender.py --to "x@y.com" --subject "Hi"  # Send quick email
    python mail_sender.py --to "x@y.com" --subject "Hi" --html  # HTML email
"""

import smtplib
import ssl
import logging
import argparse
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import List, Optional, Union

from mail_config import GMAIL_EMAIL, LOG_FILE
from gmail_oauth import get_smtp_connection  # OAuth2 XOAUTH2 auth

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


def test_smtp_connection() -> bool:
    """Test SMTP connection and return True if successful."""
    try:
        smtp = get_smtp_connection()
        smtp.quit()
        log.info("✅ SMTP connection test PASSED")
        return True
    except Exception as e:
        log.error(f"❌ SMTP connection test FAILED: {e}")
        return False


# ── Build Message ─────────────────────────────────────────────────────────────
def build_message(
    to: Union[str, List[str]],
    subject: str,
    body_text: str = "",
    body_html: str = "",
    from_name: str = "Mail Automation",
    from_email: str = None,
    cc: Union[str, List[str]] = None,
    bcc: Union[str, List[str]] = None,
    reply_to: str = None,
    attachments: List[Union[str, Path]] = None,
    in_reply_to: str = None,
    references: str = None,
) -> MIMEMultipart:
    """Build a MIME email message ready to send."""

    from_email = from_email or GMAIL_EMAIL
    from_addr = f"{from_name} <{from_email}>"

    # Normalize recipients to lists
    if isinstance(to, str):
        to = [t.strip() for t in to.split(",")]
    if isinstance(cc, str):
        cc = [c.strip() for c in cc.split(",")]
    if isinstance(bcc, str):
        bcc = [b.strip() for b in bcc.split(",")]

    # Build MIME structure
    if body_html and body_text:
        # Both text and HTML
        msg = MIMEMultipart("mixed")
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text, "plain", "utf-8"))
        alt.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt)
    elif body_html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    else:
        msg = MIMEMultipart("mixed")
        msg.attach(MIMEText(body_text or "", "plain", "utf-8"))

    # Headers
    msg["From"]    = from_addr
    msg["To"]      = ", ".join(to)
    msg["Subject"] = subject
    msg["Date"]    = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_email.split("@")[-1])

    if cc:
        msg["Cc"] = ", ".join(cc)
    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"]  = references or in_reply_to

    # Attachments
    if attachments:
        for filepath in attachments:
            filepath = Path(filepath)
            if not filepath.exists():
                log.warning(f"⚠️  Attachment not found: {filepath}")
                continue

            with open(filepath, "rb") as f:
                part = MIMEApplication(f.read(), Name=filepath.name)
            part["Content-Disposition"] = f'attachment; filename="{filepath.name}"'
            msg.attach(part)
            log.info(f"📎 Attached: {filepath.name}")

    return msg, to, cc, bcc


# ── Send Email ────────────────────────────────────────────────────────────────
def send_email(
    to: Union[str, List[str]],
    subject: str,
    body_text: str = "",
    body_html: str = "",
    from_name: str = "Mail Automation",
    from_email: str = None,
    cc: Union[str, List[str]] = None,
    bcc: Union[str, List[str]] = None,
    reply_to: str = None,
    attachments: List[Union[str, Path]] = None,
    in_reply_to: str = None,
    references: str = None,
) -> bool:
    """
    Send an email via Gmail SMTP (OAuth2).

    Args:
        to:          Recipient email(s) — string or list
        subject:     Email subject
        body_text:   Plain text body
        body_html:   HTML body (shown instead of text in HTML-capable clients)
        from_name:   Display name for sender
        from_email:  Sender email (defaults to GMAIL_EMAIL from config)
        cc:          CC recipient(s)
        bcc:         BCC recipient(s)
        reply_to:    Reply-To address
        attachments: List of file paths to attach
        in_reply_to: Message-ID of the email you're replying to
        references:  References header for threading

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        msg, to_list, cc_list, bcc_list = build_message(
            to=to, subject=subject, body_text=body_text, body_html=body_html,
            from_name=from_name, from_email=from_email, cc=cc, bcc=bcc,
            reply_to=reply_to, attachments=attachments,
            in_reply_to=in_reply_to, references=references
        )

        # All actual recipients (including BCC — SMTP-level, not in headers)
        all_recipients = to_list.copy()
        if cc_list:
            all_recipients.extend(cc_list)
        if bcc_list:
            all_recipients.extend(bcc_list)

        smtp = get_smtp_connection()
        smtp.sendmail(from_email or GMAIL_EMAIL, all_recipients, msg.as_string())
        smtp.quit()

        log.info(f"✅ Email sent → {', '.join(to_list)} | Subject: {subject}")
        return True

    except Exception as e:
        log.error(f"❌ Failed to send email to {to}: {e}")
        return False


def send_reply(
    original_email: dict,
    reply_body_text: str,
    reply_body_html: str = "",
    from_name: str = "Mail Automation"
) -> bool:
    """
    Reply to an existing email (preserves threading).

    Args:
        original_email: Dict from mail_reader.fetch_emails()
        reply_body_text: Plain text reply
        reply_body_html: HTML reply (optional)
        from_name:       Sender display name

    Returns:
        True if sent successfully
    """
    # Reply goes to original sender
    reply_to_addr = original_email.get("from", "")
    subject = original_email.get("subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    return send_email(
        to=reply_to_addr,
        subject=subject,
        body_text=reply_body_text,
        body_html=reply_body_html,
        from_name=from_name,
        in_reply_to=original_email.get("message_id"),
        references=original_email.get("message_id"),
    )


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send emails via Gmail SMTP")
    parser.add_argument("--test",    action="store_true", help="Test SMTP connection only")
    parser.add_argument("--to",      help="Recipient email address")
    parser.add_argument("--subject", default="Test from Mail Automation", help="Email subject")
    parser.add_argument("--body",    default="This is a test email from your automation setup!", help="Email body")
    parser.add_argument("--html",    action="store_true", help="Send body as HTML")
    parser.add_argument("--attach",  nargs="*", help="File paths to attach")
    args = parser.parse_args()

    if args.test:
        success = test_smtp_connection()
        sys.exit(0 if success else 1)

    if not args.to:
        print("❌ Please specify --to <email>")
        sys.exit(1)

    kwargs = {
        "to": args.to,
        "subject": args.subject,
        "attachments": args.attach
    }
    if args.html:
        kwargs["body_html"] = args.body
    else:
        kwargs["body_text"] = args.body

    success = send_email(**kwargs)
    sys.exit(0 if success else 1)
