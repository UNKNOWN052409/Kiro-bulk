# Task Notes v14 - BREAKTHROUGH

## SOLVED: OTP Extraction
- Sign-in OTP emails go to **SPAM folder** in Gmail, NOT Inbox
- Subject: "Verify your identity" from no-reply@login.awsapps.com
- Extraction: search [Gmail]/Spam folder for "Verify your identity" since last 15 min

## Device Auth Flow - Working Steps
1. Panel login: POST /api/auth/login with password 7894561230
2. Get device code: GET /api/oauth/kiro/device-code?start_url=https://view.awsapps.com/start&region=us-east-1&auth_method=idc
3. Navigate to verification_uri_complete (view.awsapps.com/start/#/device?user_code=XXX)
4. Page redirects to us-east-1.signin.aws (AWS SSO login)
5. Fill email (nicholas204@havenhaus.in) → Enter
6. Wait for password page → Fill password (wbh$b999%%EbC-) → Enter
7. OTP page appears → Extract from Spam → Enter OTP → Enter
8. "Authorization requested" page appears with device code
9. Need to click "Allow" button (might need to scroll down)

## Current Status
- The flow works up to step 8
- Step 9 (clicking Allow) is the final step
- After clicking Allow, the panel should detect the authorization

## Account Credentials
- nicholas204@havenhaus.in / wbh$b999%%EbC-
- powell707@havenhaus.in / pI6z7GxxO1iMoQ27#=

## Script Location
- /tmp/test_device_auth_final.py (the working script)

## Panel API
- Import API: POST /api/oauth/kiro/import (needs refreshToken)
- Device code: GET /api/oauth/kiro/device-code
- The panel uses its own OIDC client to get tokens after user authorizes

## Key Fix for OTP
```python
mail.select('"[Gmail]/Spam"')
status, messages = mail.search(None, f'(SINCE {since} SUBJECT "Verify your identity")')
```
