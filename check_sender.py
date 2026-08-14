"""Check the sender of the latest OTP email to mx7k2p4n8q."""
import imaplib, email
from email.utils import parsedate_to_datetime

imap = imaplib.IMAP4_SSL('imap.gmail.com')
imap.login('anshika31618@gmail.com', 'hlcv eobi tfwh terw')

# Search INBOX for emails to mx7k2p4n8q
imap.select('"INBOX"')
status, data = imap.search(None, '(TO "mx7k2p4n8q@havenhaus.in")')
print(f"Found: {data[0].split()}")

for num in data[0].split():
    resp, msg_data = imap.fetch(num, '(RFC822)')
    msg = email.message_from_bytes(msg_data[0][1])
    print(f"\nFrom: {msg.get('From')}")
    print(f"To: {msg.get('To')}")
    print(f"Date: {msg.get('Date')}")
    print(f"Subject: {msg.get('Subject')}")
    # Get body
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                import re
                codes = re.findall(r'\b\d{6}\b', body)
                if codes:
                    print(f"OTP codes found: {codes}")
                break
    else:
        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        import re
        codes = re.findall(r'\b\d{6}\b', body)
        if codes:
            print(f"OTP codes found: {codes}")

imap.logout()
