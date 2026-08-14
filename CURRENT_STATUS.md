# Current Status - Kiro Account Creation

## What's working:
- OIDC client registration (no proxy needed)
- Redirect chain: oidc.us-east-1 → view.awsapps.com → portal.sso → signin.aws (with WSH)
- Email submit API call (HTTP 200, returns new WSH + sets cookies)
- Cookies after email submit: platform-ubid, login-interview-token, workflow-step-id, workflow-csrf-token

## What's NOT working:
- Signup API call (actionId=SIGNUP on /api/execute) → ALWAYS returns HTTP 400 SIGNIN_BAD_REQUEST_ERROR
- This happens regardless of stepId value (get-identity-user, start, empty)
- This happens with or without proxy

## Key finding:
The signup call returns 400 because the workflow state is invalid. The email submit returns 200 and sets cookies. But the subsequent signup call with the new WSH fails.

## Hypothesis:
The issue might be that the signup call needs to happen on the SAME connection/session as the email submit. When using `requests.Session`, each request goes through the proxy and might get a different exit IP. The AWS server might be checking that all requests come from the same IP.

## Current approach:
Trying to use Playwright browser to capture the EXACT signup request (headers, cookies, body) to understand what's different.

## Files:
- /home/ubuntu/kiro-gen/mitm_account_creator.py - Main API-only script (signup fails with 400)
- /home/ubuntu/kiro-gen/capture_signup_exact.py - Browser-based capture of exact signup request
- /home/ubuntu/kiro-gen/test_signup_stepid.py - Tests different stepId values (all fail)
- /home/ubuntu/kiro-gen/test_signup_cookies.py - Tests cookie handling (signup still fails)

## Next step:
1. Get the browser capture working to see the exact signup request
2. Compare with our API-only request to find the difference
3. Fix the difference and test again
