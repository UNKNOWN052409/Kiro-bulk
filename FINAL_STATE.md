# FINAL STATE - Kiro Account Creation

## Current Browser State:
- Browser is LOGGED OUT (clicked Sign out from William Gupta account)
- Currently on Name page for ogybk3y9cn@havenhaus.in (from previous interrupted run)
- This is leftover state - the script should handle this

## Verified Full Flow (tested manually, 100% confirmed):
1. Navigate to OIDC authorize URL → redirects to signin.aws login page
2. **Email page**: Fill email → Click "Continue"
3. Page navigates to `profile.aws.amazon.com/?workflowID=...` → **Name page**: "Enter your name" with text input (placeholder "Maria José Silva") → Fill name → Click "Continue"
4. **OTP page** (profile.aws.amazon.com): "Verify your email" / "Verification code" (6-digit placeholder) → Fill OTP → Click "Continue"
5. **Password page**: "Create your password" with 2 password fields → Fill both → Click "Continue" (page shows "Match" when passwords match)
6. **Allow page**: "Allow kiro-XXXX to access your data?" → Click "Allow access"
7. Browser redirects to localhost callback: `http://127.0.0.1:PORT/oauth/callback?code=JWT_TOKEN`
8. Exchange code for tokens: POST `https://oidc.us-east-1.amazonaws.com/token` with JSON body

## Key Timing:
- Each page takes 10-30 seconds to render
- After clicking Continue, wait 25 seconds then check for next page
- Total per account: ~3-4 minutes

## Files:
- `final_production_v2.py` - Fixed script with state machine approach (Allow detection now checks for 'kiro-' in body)
- `extract_otp_v3.py` - OTP extraction from Gmail (anshika31618@gmail.com, app pass: hlcv eobi tfwh terw)
- `captured_tokens.json` - Results storage

## Chrome:
- CDP: http://localhost:9222
- Display: :99 (Xvfb)
- Profile: /home/ubuntu/.browser_data_dir (clean, logged out)

## Next Steps:
1. Run final_production_v2.py for 10 accounts
2. Each account creates NEW AWS Builder ID with unique OIDC token
3. Save results to captured_tokens.json
4. When panel is back up, import tokens

## Note:
- The browser currently has leftover state (Name page for ogybk3y9cn@havenhaus.in)
- The script should handle this - if it detects "Enter your name", it will fill name and continue
- But we need a FRESH account, not this leftover one
- The script's flow: if it sees "Enter your name" with an old email, it will fill a NEW name and continue with the OLD email's OTP
- This is WRONG - we need to start fresh for each account
- Solution: The script should detect if it's on a leftover page and navigate back to the login page
