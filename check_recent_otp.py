"""Check the most recent OTP email body to understand the format."""
import imaplib, email, re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

GMAIL_EMAIL = 'anshika31618@gmail.com'
GMAIL_APP_PASS = 'hlcv eobi tfwh terw'

def main():
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(GMAIL_EMAIL, GMAIL_APP_PASS)
    mail.select('[Gmail]/Spam')

    status, data = mail.search(None, '(FROM "no-reply@login.awsapps.com")')
    if not data[0]:
        print("No emails found")
        return

    msg_ids = data[0].split()
    print(f"Total OTP emails in Spam: {len(msg_ids)}")

    # Get the 5 most recent
    for msg_id in msg_ids[-5:]:
        status2, msg_data = mail.fetch(msg_id, '(RFC822)')
        if status2 != 'OK':
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        msg_date = msg.get('Date', '')
        to = msg.get('To', '')
        print(f"\n--- Email to {to}, Date: {msg_date} ---")

        dt = parsedate_to_datetime(msg_date)
        now = datetime.now(timezone.utc)
        age_min = (now - dt).total_seconds() / 60
        print(f"  Age: {age_min:.1f} minutes")

        # Get body
        body = None
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype in ['text/html', 'text/plain']:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='ignore')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='ignore')

        if body:
            clean = re.sub(r'<[^>]+>', ' ', body)
            clean = re.sub(r'\s+', ' ', clean)
            matches = re.findall(r'(?<!\d)(\d{6})(?!\d)', clean)
            print(f"  Body snippet: {clean[:200]}")
            print(f"  OTP candidates: {matches[:5]}")

    mail.logout()

if __name__ == '__main__':
    main()
