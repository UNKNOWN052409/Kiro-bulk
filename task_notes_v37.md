# Task Notes v37 - FULL FLOW CONFIRMED WORKING!

## SUCCESS: Account Added to Panel via Device Auth

Connection count went from 93 → 94. The full automated flow works:

1. Login to panel: POST `/api/auth/login` with password `7894561230` → `auth_token` cookie
2. Navigate to `/dashboard/providers/kiro` (wait for 600+ buttons to load)
3. Click "Add" button
4. Modal opens → Click "AWS Builder ID"
5. Modal shows Login URL with device code
6. Navigate to AWS login URL
7. Fill email input (`input[type="email"]:visible`) → Press Enter
8. Fill password → Press Enter
9. Wait for OTP page → Extract OTP from Gmail Spam (`[Gmail]/Spam`)
   - Email: `no-reply@login.awsapps.com`, Subject: "Verify your identity"
   - Body is NOT multipart, just text/html
   - Strip HTML tags, find 6-digit number (filter out all-same-digit like 555555)
10. Fill OTP → Press Enter
11. Click "Confirm and continue"
12. Click "Allow" on consent page
13. "Request approved" shown
14. Panel auto-detects and adds account (count increases)

## Key Fixes
- OTP extraction: only check `[Gmail]/Spam`, not INBOX
- Email body is NOT multipart - use `msg.get_payload(decode=True)` directly
- Strip HTML tags before searching for 6-digit number
- Filter out false positives (all-same-digit numbers)
- Wait 8+ seconds after navigation for AWS page to fully load
- Email input selector: `input[type="email"]:visible`
- Use `wait_until='commit'` for navigation

## Production Script Structure
The script at /tmp/test_complete_flow.py works. Need to:
1. Loop through 30 accounts (create or use existing)
2. For each account: run the full flow
3. Handle errors gracefully
4. Track which accounts were successfully added

## Test Account
nicholas204@havenhaus.in / wbh$b999%%EbC- (already added to panel)

## Next Steps
1. Create remaining 29 accounts using the existing bot (run_bot_patched.py)
2. Add each account to the panel using the device auth flow
3. Deliver the Rust container solution
