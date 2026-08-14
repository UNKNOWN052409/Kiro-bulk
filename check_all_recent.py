"""Check ALL recent emails (Inbox + Spam) from the last 30 minutes."""
import imaplib, email
from email.header import decode_header
import time

def check_folder(imap, folder):
    resp, data = imap.select(f'"{folder}"')
    if resp != 'OK':
        return []
    
    since_date = time.strftime('%d-%b-%Y', time.gmtime(time.time() - 1800))
    resp, messages = imap.search(None, '(SINCE "' + since_date + '")')
    if resp != 'OK':
        return []
    
    nums = messages[0].split()
    results = []
    for num in nums[-20:]:  # Last 20
        resp, msg_data = imap.fetch(num, '(RFC822)')
        if resp != 'OK':
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        to = msg.get('To', '')
        date = msg.get('Date', '')
        subject = msg.get('Subject', '')
        results.append(f"  To: {to} | Date: {date} | Subj: {subject[:50]}")
    return results

def main():
    imap = imaplib.IMAP4_SSL('imap.gmail.com')
    imap.login('anshika31618@gmail.com', 'hlcv eobi tfwh terw')
    
    print("=== INBOX (last 30 min) ===")
    inbox = check_folder(imap, 'INBOX')
    if inbox:
        for r in inbox:
            print(r)
    else:
        print("  No recent emails")
    
    print("\n=== SPAM (last 30 min) ===")
    spam = check_folder(imap, '[Gmail]/Spam')
    if spam:
        for r in spam:
            print(r)
    else:
        print("  No recent emails")
    
    imap.logout()

main()
