"""OTP extraction v3 - properly filters by recipient email address."""
import imaplib, email, re, socket
socket.setdefaulttimeout(10)
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

GMAIL_EMAIL = 'anshika31618@gmail.com'
GMAIL_APP_PASS = 'hlcv eobi tfwh terw'

def extract_otp_gmail_v3(target_email: str, timeout: int = 120, after_timestamp: float = None) -> str:
    """Extract OTP from Gmail - searches both Inbox and Spam, filters by exact recipient."""
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com', timeout=10)
        mail.login(GMAIL_EMAIL, GMAIL_APP_PASS)
        folders = ['INBOX', '[Gmail]/Spam']
        best_msg = None  # (timestamp, otp, folder)
        for folder in folders:
            try:
                status, data = mail.select(f'"{folder}"')
                if status != 'OK':
                    continue
                # Search emails from AWS sender TO our target email (much faster)
                status, data = mail.search(None, f'(OR (FROM "no-reply@signin.aws" TO "{target_email}") (FROM "no-reply@login.awsapps.com" TO "{target_email}"))')
                if status != 'OK' or not data[0]:
                    continue
                msg_ids = data[0].split()
                # Only check the last 10 (most recent)
                msg_ids = msg_ids[-10:]
                for msg_id in msg_ids:
                    status2, msg_data = mail.fetch(msg_id, '(RFC822)')
                    if status2 != 'OK':
                        continue
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    to_header = msg.get('To', '')
                    if target_email.lower() not in to_header.lower():
                        continue
                    msg_date = msg.get('Date', '')
                    try:
                        dt = parsedate_to_datetime(msg_date)
                        now_aware = datetime.now(timezone.utc)
                        age = (now_aware - dt).total_seconds()
                        if age > 1800:
                            continue
                        if after_timestamp and dt.timestamp() < after_timestamp:
                            continue
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == 'text/plain':
                                    body = part.get_payload(decode=True)
                                    if body:
                                        body_text = body.decode('utf-8', errors='ignore')
                                        codes = re.findall(r'\b(\d{6})\b', body_text)
                                        if codes:
                                            if best_msg is None or dt.timestamp() > best_msg[0]:
                                                best_msg = (dt.timestamp(), codes[-1], folder)
                                    break
                        else:
                            body = msg.get_payload(decode=True)
                            if body:
                                body_text = body.decode('utf-8', errors='ignore')
                                codes = re.findall(r'\b(\d{6})\b', body_text)
                                if codes:
                                    if best_msg is None or dt.timestamp() > best_msg[0]:
                                        best_msg = (dt.timestamp(), codes[-1], folder)
                    except Exception:
                        continue
            except Exception:
                continue
        mail.logout()
        if best_msg:
            return best_msg[1]
        return None
    except Exception as e:
        print(f"[!] OTP extraction error: {e}")
        return None

if __name__ == '__main__':
    import sys
    email_addr = sys.argv[1] if len(sys.argv) > 1 else '6e7suzi87g@havenhaus.in'
    otp = extract_otp_gmail_v3(email_addr)
    print(f"OTP for {email_addr}: {otp}")
