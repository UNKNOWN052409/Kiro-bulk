# Final Approach - API-Only Account Creation

## Key Findings (Aug 14, 2026)

### What Works
1. OIDC client registration: POST https://oidc.us-east-1.amazonaws.com/client/register (no proxy)
2. Getting workflowStateHandle via redirect chain (with proxy or without):
   - GET authorize URL → 302 → view.awsapps.com/start
   - Manual redirect: GET https://portal.sso.us-east-1.amazonaws.com/login?directory_id=view&orchestrator_id=XXX
   - → 302 → us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle=UUID
3. Email submit via API: POST /api/execute with actionId="SUBMIT" → HTTP 200 (works with proxy)
4. Signup via API: POST /api/execute with actionId="SIGNUP" → HTTP 200 (works with proxy)
5. Browser can navigate to profile.aws.amazon.com/?workflowID=UUID (captures workflowID)
6. get-config API: POST /api/get-config with body {} → HTTP 200 (works)

### The Problem
- /api/start returns "Invalid step. Step: ABORTED, Expected Steps: [PENDING]"
- The workflow is created by the SPA but expires/aborts when browser closes
- /api/get-app-context returns 404 "Application context not found"

### The Solution Being Tested
- Use Playwright page.evaluate() to make ALL profile.aws.amazon.com API calls
  from within the browser context (same session, cookies, TLS fingerprint)
- This keeps the workflow alive because the browser stays open
- Script: /home/ubuntu/kiro-gen/test_profile_in_browser.py

### Exact API Format (from MITM intercept)
```json
// /api/get-config
{}

// /api/get-app-context  
{"workflowID": "uuid"}

// /api/start
{
  "workflowID": "uuid",
  "browserData": {
    "attributes": {
      "fingerprint": "ECdITeCs:...(5781 chars)",
      "eventTimestamp": "2026-08-14T06:27:01.254Z",
      "timeSpentOnPage": "44",
      "eventType": "PageLoad",
      "ubid": "239-5811613-3038639"
    },
    "cookies": {}
  }
}

// Headers needed:
// Content-Type: application/json;charset=UTF-8
// Referer: https://profile.aws.amazon.com/?workflowID=uuid
// (No Origin, No Accept needed)
```

### Next Steps After start Works
1. POST /api/send-otp → get workflowState
2. Wait for OTP email from Gmail
3. Submit OTP via API
4. Submit name via API  
5. Submit password via API
6. Capture OIDC tokens

### ProxyRise
- SOCKS5: socks5://api-US:pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1@gw.proxyrise.com:443
- Works for signin.aws API calls
- Does NOT work for profile.aws.amazon.com SPA rendering (but API calls might work)

### Gmail OTP
- anshika31618@gmail.com / App Password: hlcv eobi tfwh terw
- Use IMAP to read OTP emails
