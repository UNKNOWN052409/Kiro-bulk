"""
Debug OTP extraction step by step.
"""
import imaplib, email, re
from datetime import datetime, timedelta, timezone

GMAIL_EMAIL = 'anshika31618@gmail.com'
GMAIL_APP_PASS = 'hlcv eobi tfwh terw'

def main():
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(GMAIL_EMAIL, GMAIL_APP_PASS)
    
    spam_folder = '[Gmail]/Spam'
    mail.select(f'"{spam_folder}"')
    
    # Search for recent emails (last hour)
    since_date = (datetime.now() - timedelta(hours=1)).strftime('%d-%b-%Y')
    print(f"[*] Searching SINCE {since_date}...")
    
    status, data = mail.search(None, f'(SINCE {since_date} FROM "no-reply@login.awsapps.com")')
    print(f"[*] Status: {status}, Count: {len(data[0].split()) if data[0] else 0}")
    
    if data[0]:
        msg_ids = data[0].split()
        print(f"[*] Message IDs: {msg_ids}")
        for msg_id in msg_ids:
            status2, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status2 != 'OK':
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            msg_date = msg.get('Date', '')
            msg_to = msg.get('To', '')
            print(f"  - To: {msg_to}, Date: {msg_date}")
            
            # Try to parse date
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(msg_date)
                now_aware = datetime.now(timezone.utc)
                age = (now_aware - dt).total_seconds()
                print(f"    Age: {age:.0f}s, Accept: {age < 1800}")
            except Exception as e:
                print(f"    Date parse error: {e}")
            
            # Get body and find OTP
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
                clean_text = re.sub(r'<[^>]+>', ' ', body)
                clean_text = re.sub(r'\s+', ' ', clean_text)
                matches = re.findall(r'(?<!\d)(\d{6})(?!\d)', clean_text)
                if matches:
                    print(f"    OTP candidates: {matches[:5]}")
    
    mail.logout()

if __name__ == '__main__':
    main()
