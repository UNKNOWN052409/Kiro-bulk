# STATUS V5 - Hybrid approach in mitm_account_creator.py

## Key changes made to mitm_account_creator.py:
1. Sticky session: `res-us-sid-SESSIONID` format (verified working - same IP across requests)
2. Email submit → 200 ✓
3. Signup (actionId=SIGNUP) → 200 ✓ (returns new WSH)
4. Now uses browser (headless=False, Xvfb :99) with proxy to load profile.aws.amazon.com
5. Browser calls /api/start from within page context to get workflowState
6. Then continues with API-only calls for OTP, name, password, token

## What still needs to be done in the script:
- After getting workflowState from browser's /api/start, need to:
  - Fill name in the form (browser)
  - Click Continue (browser)
  - Get OTP from Gmail
  - Fill OTP (browser or API)
  - Fill password (browser or API)
  - Click Create (browser)
  - Wait for token callback

## Current issue:
The script was updated to add browser step but the remaining flow (OTP, password, token) might still use the old API-only approach. Need to verify the full flow works end-to-end.

## Environment:
- Xvfb on :99
- Display: DISPLAY=:99
- Proxy: socks5://res-us-sid-{SESSION_ID}:{API_KEY}@gw.proxyrise.com:443
- Callback port: 9997

## Command to run:
```
DISPLAY=:99 timeout 180 python3 -u mitm_account_creator.py
```

## Gmail:
- User: anshika31618@gmail.com
- App password: hlcveobitfwh terw (remove space → hlcveobitfwh terw)

## Names/Email:
- Domain: @havenhaus.in
- Random first/last names from lists in the script
