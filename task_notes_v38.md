# Task Notes v38 - Production Script Integration Plan

## Working Flow (confirmed at /tmp/test_complete_flow.py)
The panel UI device auth flow works end-to-end:
1. Panel login → `/api/auth/login` → auth_token cookie
2. Navigate to `/dashboard/providers/kiro` (wait for 600+ buttons)
3. Click "Add" button (text contains 'Add'/'add', not 'Add Model', not 'Disable All', not 'close')
4. Modal opens → Click "AWS Builder ID" button
5. Modal shows Login URL with device code: `https://view.awsapps.com/start/#/device?user_code=XXXX-XXXX`
6. Navigate to AWS login URL (new page in same context)
7. Fill email: `input[type="email"]:visible` → fill → Enter
8. Fill password: `input[type="password"]` → fill → Enter
9. OTP page: extract from Gmail Spam `[Gmail]/Spam`
   - Body is NOT multipart, just text/html
   - Strip HTML tags, find 6-digit number
   - Filter out all-same-digit (555555) and sequential (123456)
10. Fill OTP → Enter
11. Click "Confirm and continue" (button with text "Confirm and continue")
12. Click "Allow" on consent page
13. "Request approved" → Panel auto-adds account (count 93→94)

## Production Script Issues (run_bot_patched.py)
- `poll_otp_imap()` (line 1460) only checks INBOX, not Spam
- `poll_otp_imap()` uses `fetch_emails` from mail_reader which requires gmail_oauth
- `panel_add_account()` uses `/api/oauth/kiro/device-code` API which returns `invalid_client`
- The UI device auth fallback (line 4250+) tries to get device code from API first, then falls back
- Need to replace with the modal-based approach

## Fix Strategy
1. Fix OTP extraction: check Spam folder, handle non-multipart HTML
2. Replace `panel_add_account()` with UI modal approach:
   - Click "Add" → Click "AWS Builder ID" → Extract URL from modal
   - Navigate to URL → Complete sign-in flow
3. Use Playwright (not Camoufox) for the panel interaction since we just need browser automation

## Gmail OTP Details
- Folder: `[Gmail]/Spam` (IMAP)
- Sender: `no-reply@login.awsapps.com`
- Subject: "Verify your identity"
- Body: single-part text/html (NOT multipart)
- OTP: first 6-digit number that's not all-same-digit and not sequential
- Code: `re.findall(r'(?<!\d)(\d{6})(?!\d)', clean_text)` with filters

## Panel Details
- URL: https://ourproxy.sryze.cc
- Pass: 7894561230
- Kiro page: /dashboard/providers/kiro
- 93 accounts already present (before our addition)

## Accounts
- nicholas204@havenhaus.in / wbh$b999%%EbC- (already added to panel)
- Domain: @havenhaus.in
- Need 30 total accounts

## Rust Container
- User wants Rust container instead of Docker
- 0.1 CPU core limit
- Should isolate the proxy/browser so it doesn't affect main system
