#!/usr/bin/env python3
import imaplib, email, re, time

GMAIL = 'anshika31618@gmail.com'
GMAIL_PASS = 'hlcveobitfwhterw'

mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(GMAIL, GMAIL_PASS)
mail.select('[Gmail]/Spam')
status, messages = mail.search(None, 'ALL')
msg_ids = messages[0].split()
print(f'Total in Spam: {len(msg_ids)}')

msg_id = msg_ids[-1]
status, msg_data = mail.fetch(msg_id, '(RFC822)')
msg = email.message_from_bytes(msg_data[0][1])
print(f'From: {msg.get("From")}')
print(f'Subject: {msg.get("Subject")}')

body = ''
if msg.is_multipart():
    for part in msg.walk():
        if part.get_content_type() == 'text/plain':
            payload = part.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='ignore')
                break
else:
    payload = msg.get_payload(decode=True)
    if payload:
        body = payload.decode('utf-8', errors='ignore')

print('=== BODY ===')
print(body[:3000])
print()
codes = re.findall(r'\b([A-Z]{4}-[A-Z]{4})\b', body)
print(f'4-4 codes: {codes}')
digits = re.findall(r'\b(\d{6})\b', body)
print(f'6-digit: {digits}')
mail.logout()
