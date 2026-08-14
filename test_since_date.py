"""
Test the IMAP SINCE date search.
"""
import imaplib, email
from datetime import datetime, timedelta

GMAIL_EMAIL = 'anshika31618@gmail.com'
GMAIL_APP_PASS = 'hlcv eobi tfwh terw'

def main():
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(GMAIL_EMAIL, GMAIL_APP_PASS)
    
    # Check current time
    now = datetime.now()
    print(f"[*] Current time: {now}")
    
    # What does the since_date look like?
    since_date = (datetime.now() - timedelta(minutes=60)).strftime('%d-%b-%Y')
    print(f"[*] Since date (60min ago): {since_date}")
    
    # Also check with -5 min buffer
    since_dt2 = datetime.fromtimestamp(1786620139.6927552) - timedelta(seconds=30)
    since_date2 = since_dt2.strftime('%d-%b-%Y')
    print(f"[*] Since date (from timestamp): {since_date2}")
    
    # Search Spam
    mail.select('[Gmail]/Spam')
    status, data = mail.search(None, f'(SINCE {since_date} FROM "no-reply@login.awsapps.com")')
    count = len(data[0].split()) if data[0] else 0
    print(f"[*] SINCE {since_date}: {count} emails")
    
    # Search all
    status, data = mail.search(None, '(FROM "no-reply@login.awsapps.com")')
    count = len(data[0].split()) if data[0] else 0
    print(f"[*] ALL: {count} emails")
    
    # Check the latest email's date
    if data[0]:
        msg_ids = data[0].split()
        latest = msg_ids[-1]
        status2, msg_data = mail.fetch(latest, '(RFC822.HEADER)')
        if status2 == 'OK':
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            print(f"[*] Latest email date: {msg.get('Date')}")
    
    mail.logout()

if __name__ == '__main__':
    main()
