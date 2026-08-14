# Current State - Kiro Account Creation

## Key Findings (verified):
1. The full signup flow is: **Email → Name → Password → OTP → Allow → Token capture**
2. The Name step was MISSING from the original script, causing all accounts to fail
3. After entering email, the page shows "Enter your name" at `profile.aws.amazon.com/?workflowID=...`
4. The name input is `type=text` with placeholder "Maria José Silva"
5. The SPA takes 50-75 seconds to render each page
6. Browser now has CLEAN profile (cookies cleared)

## Current Script:
- `/home/ubuntu/kiro-gen/final_production.py` - Updated with Name step
- Uses OIDC Authorization Code Flow with PKCE
- Registers client at `https://oidc.us-east-1.amazonaws.com/client/register`
- Navigates to `https://oidc.us-east-1.amazonaws.com/authorize`
- After Allow, redirects to localhost callback with auth code
- Exchanges code for tokens at `https://oidc.us-east-1.amazonaws.com/token`

## OTP Extraction:
- Gmail: anshika31618@gmail.com
- App password: hlcv eobi tfwh terw
- Function: `extract_otp_gmail_v3(target_email)` from extract_otp_v3.py

## Chrome Status:
- Running with clean profile at `/home/ubuntu/.browser_data_dir`
- CDP port: 9222
- Xvfb display: :99
- Memory is fine (2.7GB+ available)

## Next Steps:
1. Run `final_production.py 10` to create 10 accounts with full flow
2. Check captured_tokens.json for results
3. Repeat until we have 30 accounts total (need ~10 more since some earlier accounts have tokens)
4. Once panel is back up, import tokens via POST to /api/oauth/kiro/import

## Panel Info (when back up):
- URL: https://ourproxy.sryze.cc/dashboard/providers
- Provider: kiro, Password: 7894561230
- API: POST /api/oauth/kiro/import
- Body: {"refreshToken": "...", "region": "us-east-1", "authMethod": "builder-id", "startUrl": "https://view.awsapps.com/start", "name": "email"}
