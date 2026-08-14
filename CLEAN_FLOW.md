# Clean Browser Flow - Final Understanding

## The OIDC Authorize URL redirects to the SIGN-IN page
With a clean browser (no existing session), the OIDC authorize URL redirects to:
`https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle=...`

The page shows:
- "Get started"
- "Email" input
- "Continue" button
- "OR Continue with Google/Apple/GitHub/Amazon"
- "By continuing, you will create an AWS Builder ID."

## Full Signup Flow (clean browser):
1. **Email page**: Enter email → click "Continue"
2. **Password page**: "Create your password" with two password fields → fill both → click "Continue"
3. **OTP page**: "Check your email" / "One-time password" → extract OTP from Gmail → fill → click "Verify"
4. **Confirm page**: "Confirm and continue" → click
5. **Allow page**: "Allow access" → click
6. **Token captured**: Browser redirects to localhost callback with auth code

## Key timing:
- Each page takes 50-75 seconds to render (SPA)
- Total per account: ~3-4 minutes
- Must wait for `readyState === 'complete'` AND `body.innerText.length > 50`

## OTP extraction:
- Gmail: anshika31618@gmail.com
- App password: hlcv eobi tfwh terw
- Function: `extract_otp_gmail_v3(target_email)` from extract_otp_v3.py

## Password requirements (AWS Builder ID):
- 8+ characters
- At least one uppercase
- At least one lowercase
- At least one number
- At least one special character (!@#$%)
- Working format: "TestPass1234!" (11 chars, all requirements met)

## Current state:
- Chrome running with CLEAN profile (cookies cleared)
- Browser is at about:blank or cookie dialog
- Script: final_production.py (updated with email step)
- Output: captured_tokens.json and captured_tokens.csv

## What's next:
1. Run final_production.py for 10 accounts
2. Each account should now work with the full flow (email → password → OTP → Allow → token)
3. Once we have tokens, import to panel when it's back up
