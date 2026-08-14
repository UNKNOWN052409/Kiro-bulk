# Task Notes v33 - Complete State Summary

## What Works
1. Account creation with Builder ID (@havenhaus.in) - fully working
2. OTP extraction from Gmail Spam folder (body_html field, not body)
3. Device auth flow: email → password → OTP → Confirm → Allow → "Request approved"
4. Panel login: POST /api/auth/login with {"password": "7894561230"}
5. Panel device code: GET /api/oauth/kiro/device-code?start_url=...&region=us-east-1&auth_method=idc
6. Panel import API: POST /api/oauth/kiro/import with {"refreshToken": "..."}

## What Doesn't Work
- Panel poll endpoint: POST /api/oauth/kiro/poll with {"deviceCode": "..."} returns "invalid_client"
- Direct token exchange from Kiro auth server: 400 {"Message":null}
- Direct token exchange from AWS OIDC: 403 AccessDenied
- Social flow (Google): Accounts are Builder ID only, can't use Google sign-in

## Key Account Credentials
- nicholas204@havenhaus.in / wbh$b999%%EbC-
- powell707@havenhaus.in / (check kiro_accounts.csv)

## Panel Info
- URL: https://ourproxy.sryze.cc
- Password: 7894561230
- Already has 94 Kiro connections (4 active)
- Panel is "9Router - AI Infrastructure Management"

## The Core Problem
The panel's device auth flow requires the panel's server to exchange the device code for tokens. The panel's server uses its own client credentials. When we complete the device auth flow externally (not through the panel's UI), the panel's server doesn't know to poll. The poll endpoint returns "invalid_client" because the panel's client is being rejected by AWS.

## Possible Solutions Not Yet Tried
1. Use the panel's UI directly (navigate to dashboard, find "Add Account" for Kiro AI)
2. Try to trigger the panel's internal polling by calling the device-code endpoint and then immediately completing the auth
3. Check if the panel has a "webhook" or "callback" mechanism for device auth completion
4. Try using the Kiro app's own API to get tokens after account creation

## Scripts Location
- /tmp/test_poll_import.py - device auth + poll (OTP extraction works)
- /tmp/test_token_exchange.py - device auth + direct token exchange
- /tmp/test_social_flow.py - social flow test

## OTP Extraction (working)
```python
def extract_otp():
    from html import unescape
    def strip_html(html):
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    emails = fetch_emails(folder='[Gmail]/Spam', unread_only=True, limit=2)
    for email in emails:
        subject = email.get('subject', '') or ''
        if 'verify' not in subject.lower():
            continue
        html = email.get('body_html', '') or ''
        if not html:
            continue
        text = strip_html(html)
        match = re.search(r'\b(\d{6})\b', text)
        if match:
            code = match.group(1)
            if code not in '31618':
                return code
    return None
```
