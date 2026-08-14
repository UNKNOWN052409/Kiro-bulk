# Task Notes v36 - Full Panel Flow Working (Almost)

## BREAKTHROUGH: Panel Device Auth Modal
The 9Router panel has a "Connect Kiro" modal that provides the full device auth flow:
1. Navigate to `/dashboard/providers/kiro` (wait 30-45s for full load, 600+ buttons means loaded)
2. Click "Add" button (JS: `b.textContent.trim()` contains 'Add' or 'add', not 'Add Model', not 'Disable All', not 'close')
3. Modal opens with auth options
4. Click "AWS Builder ID" button
5. Modal shows "Connect Kiro AI" with Login URL and User Code
6. Login URL format: `https://view.awsapps.com/start/#/device?user_code=XXXX-XXXX`

## AWS Login Page Structure
- Page title: "Amazon Web Services"
- Email input: `input[type="email"]` with dynamic ID like `formField14-XXXXXXXXXXX-XXXX`
- After email + Enter → Password page
- Password input: `input[type="password"]`
- After password + Enter → OTP page ("Verify your identity")
- OTP input: text input
- After OTP + Enter → "Authorization requested" page → Click "Confirm"
- Then consent page → Click "Allow"
- Final: "Request approved"

## AWS Login Page Selectors (confirmed working)
- Email: `input[type="email"]:visible` (has dynamic ID, placeholder "username@example.com")
- Continue button: visible after email filled
- Password: `input[type="password"]`
- OTP: text input on "Verify your identity" page

## OTP Extraction Issues
- OTP emails go to SPAM folder
- Sender: `no-reply@login.awsapps.com`
- Subject: "Verify your identity"
- **Problem**: Previous extraction got wrong OTP "555555" - need to search SINCE today
- Spam folder in Gmail IMAP: `[Gmail]/Spam`

## Test Account (working)
- nicholas204@havenhaus.in / wbh$b999%%EbC-

## Panel Login
- POST `/api/auth/login` with `{"password": "7894561230"}` → `auth_token` cookie

## Panel API
- After auth completes, panel polls and should auto-add the account
- `/api/oauth/kiro/device-code` - gets device code params
- `/api/oauth/kiro/poll` - polls for token
- `/api/oauth/kiro/import` - imports with refresh token

## Current Script: /tmp/test_complete_flow.py
- Full flow: Panel login → Navigate → Click Add → Click AWS Builder ID → Extract URL → Navigate to AWS → Sign in → OTP → Confirm → Allow
- Still need to fix OTP extraction (get correct 6-digit code from most recent email)

## Key Files
- /tmp/test_complete_flow.py - main flow test
- /tmp/test_add_click2.py - panel UI exploration
- /home/ubuntu/kiro-gen/task_notes_v34.md - panel UI structure
- /home/ubuntu/kiro-gen/task_notes_v35.md - modal discovery
- /home/ubuntu/kiro-gen/run_bot_patched.py - original bot
