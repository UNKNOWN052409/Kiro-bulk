# Task Notes v34 - Panel UI Add Button Found

## Key Finding
The 9Router panel's Kiro AI detail page (`/dashboard/providers/kiro`) has a single "Add" button for adding new connections. It's located at the bottom of the connections list.

## Panel Structure
- URL: `https://ourproxy.sryze.cc/dashboard/providers/kiro`
- Login: POST `/api/auth/login` with `{"password": "7894561230"}` → sets `auth_token` cookie
- Cookie name: `auth_token`, domain: `ourproxy.sryze.cc`, HttpOnly, Secure
- Cookie file: `/tmp/panel_cookies_ui.txt` (Netscape format with `#HttpOnly_` prefix)

## Page Elements
- "Connections" section with 93 accounts (Account 1-93, all disabled/OAuth)
- "Add" button: text="addAdd", rect at bottom of connections list
- "Add Model" button: for adding models (not what we want)
- Each account has: Edit, Delete buttons, and lock icon

## Next Steps
1. Click the "Add" button → should open device auth flow
2. The panel likely opens the AWS device auth page in a new tab/popup
3. Complete the sign-in (email → password → OTP → Allow)
4. Panel should detect and add the account

## OTP Issue Solved
- OTP emails go to SPAM folder, not Inbox
- Sender: `no-reply@login.awsapps.com` (NOT `no-reply@signin.aws`)
- Subject: "Verify your identity"
- OTP is a 6-digit code in `body_html` field

## Account Credentials (for testing)
- nicholas204@havenhaus.in / wbh$b999%%EbC-

## Working Device Auth Flow
1. POST `/api/oauth/kiro/device-code` → get device_code, user_code, clientId, clientSecret
2. Navigate to `https://view.awsapps.com/start/#/device?user_code={user_code}`
3. Fill email → Continue → Fill password → Submit
4. Wait for OTP page → Extract OTP from Gmail Spam folder
5. Fill OTP → Submit
6. Click "Confirm" button (on "Authorization requested" page)
7. Click "Allow" button (on consent page "Allow kiro-oauth-client to access your data?")
8. Page shows "Request approved"

## Panel APIs
- POST `/api/oauth/kiro/device-code` → returns device code flow params
- POST `/api/oauth/kiro/poll` with `{"deviceCode": "..."}` → polls for token (returns "invalid_client" from our side)
- POST `/api/oauth/kiro/import` with `{"refreshToken": "..."}` → imports account (needs valid refresh token)

## Key URLs
- Panel: https://ourproxy.sryze.cc
- AWS device auth: https://view.awsapps.com/start/#/device
- AWS sign-in: https://us-east-1.signin.aws (SSO)
- Kiro auth server: https://prod.us-east-1.auth.desktop.kiro.dev
- Kiro app: https://app.kiro.dev
