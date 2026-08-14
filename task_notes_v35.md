# Task Notes v35 - Panel Device Auth Modal FOUND!

## Key Breakthrough
The 9Router panel has a "Connect Kiro" modal that provides the full device auth flow:
1. Click "Add" button on `/dashboard/providers/kiro`
2. Modal opens with auth method options
3. Click "AWS Builder ID"
4. Modal shows "Connect Kiro AI" with Login URL and User Code
5. Navigate to the Login URL and complete AWS auth
6. Panel polls and detects the token, adding the account

## Modal Content After Clicking "AWS Builder ID"
- Title: "Connect Kiro AI"
- "Visit the login URL below and authorize:"
- Login URL: `https://view.awsapps.com/start/#/device?user_code=XXXX-XXXX`
- "Your Code": XXXX-XXXX
- Copy button and "Open in new tab" button

## Flow Steps
1. Login to panel: POST `/api/auth/login` with password
2. Navigate to `/dashboard/providers/kiro`
3. Wait for page to fully load (~30s, 600+ buttons means loaded)
4. Click "Add" button (text: 'addAdd')
5. Modal opens with auth options
6. Click "AWS Builder ID" button
7. Modal shows device code and login URL
8. Navigate to login URL (in same or new browser context)
9. Complete AWS SSO sign-in: email → password → OTP (from Gmail Spam) → Confirm → Allow
10. Panel automatically detects and adds the account

## OTP Info
- Sign-in OTP emails go to SPAM folder
- Sender: `no-reply@login.awsapps.com`
- Subject: "Verify your identity"
- OTP: 6-digit code in `body_html` field

## Panel Login
- URL: `https://ourproxy.sryze.cc/api/auth/login`
- Password: `7894561230`
- Cookie: `auth_token` (HttpOnly, Secure, domain: ourproxy.sryze.cc)

## Page Load Notes
- Must wait 30-45s for SPA to fully load (600+ buttons means loaded)
- Need to scroll to trigger lazy loading
- Use `wait_until='commit'` for navigation (not 'domcontentloaded')
