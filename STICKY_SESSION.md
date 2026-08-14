# ProxyRise Sticky Session - SOLVED!

## Format: res-us-sid-SESSIONID
- Username: `res-us-sid-54321`
- Password: API key
- Endpoint: gw.proxyrise.com:443
- Protocol: socks5://

## Verified:
- All 3 consecutive requests got SAME IP: 99.95.61.105 (AT&T)
- Without -sid-, each request gets different IP (Comcast Orlando, Comcast Mount Prospect, Cox Baton Rouge, etc.)

## Why this fixes the signup 400:
- AWS ties workflow state to IP address
- Without sticky session, email submit comes from IP-A, signup comes from IP-B
- AWS rejects because IP changed mid-workflow
- With sticky session, ALL requests come from same IP

## Also found from ProxyRise docs:
- `stc-us` = Static ISP Residential (fixed IPs, even better for automation)
- `res-us-Lsid-ID-TTL-3600` = Long Session (up to 1 hour)
- Session IDs must be numeric 10000-999999999
- Each account creation should use a unique session ID

## Full API flow (from MITM capture):
1. OIDC client register (no proxy) → client_id
2. Follow redirects: oidc → view.awsapps.com → portal.sso → signin.aws (get WSH from portal HTML)
3. POST /api/execute: stepId="get-identity-user", actionId="SUBMIT", email → 200, new WSH + cookies
4. POST /api/execute: stepId="start", actionId="SIGNUP" → 200, new WSH (redirects to /signup)
5. GET /signup?workflowStateHandle=WSH → establishes session
6. POST /signup/api/execute: stepId="" → 200, new WSH
7. POST /signup/api/execute: stepId="start" → 200, redirects to profile.aws.amazon.com with workflowID
8. Profile SPA calls: get-config, get-app-context, start → 200
9. Fill name, submit → /api/send-otp → OTP sent
10. Get OTP from Gmail, submit → password page
11. Set password → token captured

## Key: ALL requests must use the same sticky session ID!
