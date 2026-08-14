# Issue: /signup/api/execute returns 400 SIGNIN_BAD_REQUEST_ERROR

## What we know:
- Email submit (POST /api/execute, actionId=SUBMIT) → HTTP 200 ✓
- Signup (POST /api/execute, actionId=SIGNUP) → HTTP 200, returns new WSH ✓
- GET /signup?workflowStateHandle=NEW_WSH → HTTP 200 ✓
- POST /signup/api/execute (stepId="") → HTTP 400 SIGNIN_BAD_REQUEST_ERROR ✗
- POST /signup/api/execute (stepId="start") → HTTP 400 SIGNIN_BAD_REQUEST_ERROR ✗

## Possible causes:
1. **Cookies missing** - The browser sends AWS cookies (like `csm-hit`, `aws-userInfo-signed`, etc.) with each request. Our requests.Session might not have these cookies because we never set them.
2. **WSH mismatch** - The WSH from the signup response might need to be used differently.
3. **Missing cookies from /signup page GET** - When the browser navigates to /signup?workflowStateHandle=XXX, the server sets cookies. Our GET request might not be receiving/setting these cookies.
4. **Proxy IP change** - Each request through ProxyRise might get a different exit IP, causing session mismatch.

## Key observation from MITM data:
The browser sends cookies with every request. The cookies include:
- `csm-hit`: CSRF-like token
- `aws-userInfo-signed`: Signed user info
- `x-amz-sso_authn`: SSO auth token

The requests.Session doesn't have these cookies because we never went through the proper login flow that sets them.

## Solution approach:
1. After the GET /signup page request, check what cookies are set by the response
2. Those cookies need to be included in the subsequent POST to /signup/api/execute
3. OR: The cookies might already be in the session (from the portal.sso/login redirects)

## Next step:
Check what cookies the session has after the full redirect chain, and what cookies the /signup page sets.
