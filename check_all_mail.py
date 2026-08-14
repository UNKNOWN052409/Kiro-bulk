"""Check all recent emails in Spam folder."""
import imaplib, email
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

GMAIL_EMAIL = 'anshika31618@gmail.com'
GMAIL_APP_PASS = 'hlcv eobi tfwh terw'

mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(GMAIL_EMAIL, GMAIL_APP_PASS)
mail.select('[Gmail]/Spam')

status, data = mail.search(None, 'ALL')
if data[0]:
    msg_ids = data[0].split()
    print(f"Total emails in Spam: {len(msg_ids)}")
    for msg_id in msg_ids[-10:]:
        status2, msg_data = mail.fetch(msg_id, '(RFC822.HEADER)')
        if status2 == 'OK':
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            dt = parsedate_to_datetime(msg.get('Date'))
            now = datetime.now(timezone.utc)
            age = (now - dt).total_seconds() / 60
            print(f"  Age: {age:.0f}min | From: {msg.get('From')[:40]} | To: {msg.get('To')[:40]} | Subj: {msg.get('Subject')[:40]}")

mail.logout()
