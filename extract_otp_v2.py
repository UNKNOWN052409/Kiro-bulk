"""Improved OTP extraction - searches both Inbox and Spam, handles both sender addresses."""
import imaplib, email, re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

GMAIL_EMAIL = 'anshika31618@gmail.com'
GMAIL_APP_PASS = 'hlcv eobi tfwh terw'

def extract_otp_gmail_v2(target_email: str, timeout: int = 120, after_timestamp: float = None) -> str:
    """Extract OTP from Gmail - searches both Inbox and Spam."""
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_EMAIL, GMAIL_APP_PASS)
        
        folders = ['INBOX', '[Gmail]/Spam']
        all_msgs = []
        
        for folder in folders:
            try:
                status, data = mail.select(f'"{folder}"')
                if status != 'OK':
                    continue
                
                # Search by recipient
                status, data = mail.search(None, f'(TO "{target_email}")')
                if status != 'OK' or not data[0]:
                    # Fallback: search by sender
                    status, data = mail.search(None, '(OR (FROM "no-reply@signin.aws") (FROM "no-reply@login.awsapps.com"))')
                
                if status != 'OK' or not data[0]:
                    continue
                
                msg_ids = data[0].split()
                for msg_id in msg_ids:
                    status2, msg_data = mail.fetch(msg_id, '(RFC822)')
                    if status2 != 'OK':
                        continue
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    msg_date = msg.get('Date', '')
                    try:
                        dt = parsedate_to_datetime(msg_date)
                        now_aware = datetime.now(timezone.utc)
                        age = (now_aware - dt).total_seconds()
                        
                        # Skip emails older than 30 minutes
                        if age > 1800:
                            continue
                        
                        # If after_timestamp set, skip emails before that
                        if after_timestamp and dt.timestamp() < after_timestamp:
                            continue
                        
                        # Extract OTP from body
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == 'text/plain':
                                    body = part.get_payload(decode=True)
                                    if body:
                                        body_text = body.decode('utf-8', errors='ignore')
                                        codes = re.findall(r'\b(\d{6})\b', body_text)
                                        if codes:
                                            all_msgs.append((dt.timestamp(), codes[-1], folder))
                                    break
                        else:
                            body = msg.get_payload(decode=True)
                            if body:
                                body_text = body.decode('utf-8', errors='ignore')
                                codes = re.findall(r'\b(\d{6})\b', body_text)
                                if codes:
                                    all_msgs.append((dt.timestamp(), codes[-1], folder))
                    except Exception:
                        continue
            except Exception:
                continue
        
        mail.logout()
        
        if all_msgs:
            # Return the most recent OTP
            all_msgs.sort(key=lambda x: x[0], reverse=True)
            return all_msgs[0][1]
        
        return None
    except Exception as e:
        print(f"[!] OTP extraction error: {e}")
        return None

if __name__ == '__main__':
    import sys
    email_addr = sys.argv[1] if len(sys.argv) > 1 else 'mx7k2p4n8q@havenhaus.in'
    otp = extract_otp_gmail_v2(email_addr)
    print(f"OTP for {email_addr}: {otp}")
