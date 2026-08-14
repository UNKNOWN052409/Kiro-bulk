# Debug: Login Page Not Rendering (Aug 13, 2026)

## Issue
After logout, the OIDC authorize URL redirects to `https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowState=...`. The page title shows "Amazon Web Services" but the body is EMPTY and no buttons are visible.

## Root Cause
The login page at `signin.aws` uses Shadow DOM or iframes. The `document.body.innerText` returns empty because the content is inside a Shadow Root or iframe that `page.evaluate` can't access directly.

## Evidence
- URL: `https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowState=...`
- Title: "Amazon Web Services" (page IS loaded)
- Body text: empty (content is in Shadow DOM / iframe)
- Buttons: empty (same reason)

## Solution
Need to use different selectors to access the content inside Shadow DOM or iframes:
- Use `page.frame_locator()` to access iframes
- Use `page.locator()` with specific selectors that work across Shadow DOM boundaries
- Or use `page.content()` to get the raw HTML and parse it

## Previous Working Approach
In earlier successful tests (capture_token_v2.py), the flow worked because:
1. The browser already had an active session (no logout needed)
2. The OIDC authorize URL showed the "Allow" page directly (no login needed)

## Key Finding
The login page at signin.aws is a different application from the SSO portal (view.awsapps.com). It uses a different rendering mechanism. The `document.body.innerText` doesn't work there.

## Fix for Batch Script
Instead of checking `document.body.innerText`, use:
1. `page.locator('input').count()` to check if input fields exist
2. `page.locator('button').count()` to check if buttons exist
3. `page.content()` to get raw HTML and check for specific strings
4. Or use `page.frame_locator('iframe').locator('body')` for iframe content

## Also Important
- The earlier batch run (before logout was added) worked because the browser was already logged in
- After adding logout, the browser goes to the signin.aws login page which doesn't render in `innerText`
- The successful test (test_oidc_auth_code_flow.py earlier) worked because it used the SSO portal session

## Recommendation
1. Don't logout after each account - instead, keep the session and create accounts sequentially
2. OR: Fix the selectors to work with the signin.aws login page (Shadow DOM / iframe)
3. OR: After logout, navigate to the SSO portal first (view.awsapps.com/start) which has the standard login page, then the OIDC authorize will work
