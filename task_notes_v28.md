# Task Notes v28 - OTP Extraction Fix

## Key Finding
The fetch_emails function returns email dicts with:
- `body_text`: empty string (plain text body)
- `body_html`: HTML body (contains the OTP)

The OTP is in `body_html`, NOT `body`! I need to:
1. Extract text from HTML (strip tags)
2. Search for 6-digit code in the extracted text

## Fix for extract_otp
```python
import re
from html import unescape

def extract_text_from_html(html):
    """Extract text from HTML."""
    # Remove script/style
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
    # Remove tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Decode entities
    text = unescape(text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_otp():
    for folder in ['[Gmail]/Spam']:
        emails = fetch_emails(folder=folder, unread_only=False, limit=3)
        for email in emails[:2]:
            subject = email.get('subject', '') or ''
            if 'verify' not in subject.lower():
                continue
            html = email.get('body_html', '') or ''
            text = extract_text_from_html(html)
            # Look for 6-digit code
            match = re.search(r'\b(\d{6})\b', text)
            if match:
                code = match.group(1)
                if code not in '31618':
                    return code
    return None
```

## Also Important
- The sign-in flow for nicholas204@havenhaus.in with password `wbh$b999%%EbC-` WORKS
- The OTP page appears after password submit
- The OTP is sent to Spam folder from no-reply@login.awsapps.com
- Subject: "Verify your identity"
