# ALL CRITICAL FINDINGS - Kiro Account Creation

## ProxyRise Sticky Session (SOLVED!)
- Format: `res-us-sid-SESSIONID` where SESSIONID is numeric 10000-999999999
- Example: `socks5://res-us-sid-54321:pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1@gw.proxyrise.com:443`
- Verified: 3 consecutive requests got SAME IP (99.95.61.105 AT&T)
- Without -sid-, each request gets DIFFERENT IP (this was causing the 400 error!)

## What works (API-only with sticky session):
1. OIDC client register → client_id ✓
2. Redirect chain: oidc authorize → view.awsapps.com (get orchestrator_id) → portal.sso (get WSH from HTML) → signin.aws
3. POST /api/execute: stepId="get-identity-user", actionId="SUBMIT", email → HTTP 200, new WSH ✓
4. POST /api/execute: stepId="get-identity-user", actionId="SIGNUP" → HTTP 200, new WSH + stepId="start" ✓
5. GET /signup page → HTTP 200 ✓

## What fails:
6. POST /signup/api/execute (stepId="") → 400 (needs browser SPA to initialize)
7. POST /signup/api/execute (stepId="start") → 400

## Current approach:
After signup returns new WSH, skip /signup/api/execute and go directly to profile.aws.amazon.com using the signup WSH as workflowID. The profile API calls (get-config, get-app-context, start) work through the proxy.

## Key API endpoints:
- `https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute` - email submit, signup
- `https://profile.aws.amazon.com/api/get-config` - {} → 200
- `https://profile.aws.amazon.com/api/get-app-context` - {workflowID} → 200
- `https://profile.aws.amazon.com/api/start` - {workflowID, browserData} → 200 (returns workflowState)
- `https://profile.aws.amazon.com/api/send-otp` - {workflowState, email, browserData} → 200

## browserData format for profile APIs:
```json
{
  "attributes": {
    "fingerprint": "ECdITeCs:...(long base64 string)",
    "eventTimestamp": "2024-01-01T00:00:00.000Z",
    "timeSpentOnPage": "41",
    "eventType": "PageLoad",
    "ubid": "118-123456-7890123"
  },
  "cookies": {}
}
```

## Gmail OTP:
- User: anshika31618@gmail.com
- App password: hlcveobitfwh terw (remove space → hlcveobitfwh terw)

## Next steps:
1. Test profile API calls with signup WSH as workflowID
2. If that works, fill name, get OTP, submit
3. If workflowID needs to be different, need to figure out how it's generated

## Files:
- /home/ubuntu/kiro-gen/mitm_account_creator.py - Main script (updated to skip /signup/api/execute)
- /home/ubuntu/kiro-gen/STICKY_SESSION.md - ProxyRise sticky session docs
- /home/ubuntu/kiro-gen/API_FLOW_FINAL.md - Complete API flow
