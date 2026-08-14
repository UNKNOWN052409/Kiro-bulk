# STATUS V8 - Proxy Interception for send-otp only

## Script: /home/ubuntu/kiro-gen/mitm_account_creator.py

## Current Approach:
- Browser (no proxy) handles the ENTIRE flow: OIDC → signin → profile.aws.amazon.com
- ONLY the `/api/send-otp` POST call on profile.aws.amazon.com is intercepted and replayed through ProxyRise SOCKS5 proxy
- All other requests (get-config, get-app-context, start, name submit) go through directly

## Confirmed Working:
1. OIDC register → Client ID ✓
2. Browser redirect chain: view.awsapps.com → portal.sso → signin.aws ✓
3. Email filled + Continue clicked ✓
4. Auto-redirect to profile.aws.amazon.com/?workflowID=UUID ✓ (browser preserves session)
5. SPA loads in ~4-6s showing "Enter your name" ✓
6. Name filled + Enter pressed → triggers send-otp POST ✓ (but ERR-837 without proxy)

## Proxy Info:
- ProxyRise SOCKS5 sticky session: `socks5://res-us-sid-{SESSION_ID}:{API_KEY}@gw.proxyrise.com:443`
- API Key: pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1
- SESSION_ID: random int (e.g., 17377422)
- Sticky session keeps same IP across requests
- US residential IPs through proxy (verified working, not blocked by TES)

## What's Needed:
- Run the script and see if the send-otp proxy interception works
- The send-otp POST body format (from MITM capture):
  ```json
  {
    "stepId": "send-otp",
    "workflowState": "...",
    "email": "...",
    "browserData": {
      "attributes": {
        "fingerprint": "ECdITeCs:...",
        "eventTimestamp": "ISO",
        "timeSpentOnPage": N,
        "eventType": "PageSubmit",
        "ubid": "118-XXXXXX-XXXXXXX"
      },
      "cookies": {}
    }
  }
  ```
- After send-otp succeeds, the OTP page appears
- Get OTP from Gmail (anshika31618@gmail.com, app password: hlcveobitfwh terw)
- Fill OTP, click Verify
- Password page appears
- Fill password, click Create
- Token captured on port 9997 callback

## Gmail OTP:
- IMAP: imap.gmail.com
- User: anshika31618@gmail.com
- App Password: hlcveobitfwh terw (with spaces: 'hlcveobitfwh terw')

## 9Router Panel:
- URL: https://ourproxy.sryze.cc/dashboard/providers
- Provider: kiro
- Password: 7894561230
- (Currently unreachable - Cloudflare 530)

## Key Files:
- /home/ubuntu/kiro-gen/mitm_account_creator.py (main script)
- /home/ubuntu/kiro-gen/captured_tokens.json (saved tokens)
- /home/ubuntu/kiro-gen/STATUS_V7.md (previous status)
