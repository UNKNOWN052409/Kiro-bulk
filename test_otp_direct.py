"""
Direct OTP test - check if emails are arriving at all.
"""
import imaplib, email, re
from datetime import datetime, timedelta, timezone

GMAIL_EMAIL = 'anshika31618@gmail.com'
GMAIL_APP_PASS = 'hlcv eobi tfwh terw'

def main():
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(GMAIL_EMAIL, GMAIL_APP_PASS)
    
    # List all folders
    status, data = mail.list()
    print("Folders:")
    for item in data:
        if isinstance(item, bytes):
            item = item.decode('utf-8', errors='ignore')
        print(f"  {item}")
    
    # Check Spam
    mail.select('[Gmail]/Spam')
    status, data = mail.search(None, '(FROM "no-reply@login.awsapps.com")')
    print(f"\nSpam search: status={status}, count={len(data[0].split()) if data[0] else 0}")
    
    if data[0]:
        msg_ids = data[0].split()
        # Show last 5 emails
        for msg_id in msg_ids[-5:]:
            status2, msg_data = mail.fetch(msg_id, '(RFC822.HEADER)')
            if status2 == 'OK':
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                print(f"  - From: {msg.get('From', 'N/A')}, To: {msg.get('To', 'N/A')}, Date: {msg.get('Date', 'N/A')}, Subject: {msg.get('Subject', 'N/A')[:50]}")
    
    # Check Inbox too
    mail.select('INBOX')
    status, data = mail.search(None, '(FROM "no-reply@login.awsapps.com")')
    print(f"\nInbox search: status={status}, count={len(data[0].split()) if data[0] else 0}")
    
    if data[0]:
        msg_ids = data[0].split()
        for msg_id in msg_ids[-5:]:
            status2, msg_data = mail.fetch(msg_id, '(RFC822.HEADER)')
            if status2 == 'OK':
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                print(f"  - From: {msg.get('From', 'N/A')}, To: {msg.get('To', 'N/A')}, Date: {msg.get('Date', 'N/A')}, Subject: {msg.get('Subject', 'N/A')[:50]}")
    
    mail.logout()

if __name__ == '__main__':
    main()
