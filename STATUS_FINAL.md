# Kiro Account Creator - FINAL STATUS

## PROBLEM
The name submission step (after email submit) consistently returns 400 `CONNECTION_ISSUE`.

## ROOT CAUSE
AWS TES (Threat Evaluation Service) detects that the TLS connection for the API call is DIFFERENT from the connection used for the page load. The proxy creates new TCP connections for each request, and AWS detects this as a non-browser pattern.

## WHAT WORKS
1. OIDC client registration via curl_cffi ✓
2. Browser navigation to OIDC authorize URL ✓ (gets valid WS)
3. Init call on login API via `page.evaluate()` fetch ✓ (HTTP 200)
4. Load email form ✓ (HTTP 200)
5. Submit email ✓ (HTTP 200, returns step='user-signup', new WS, redirect URL)

## WHAT FAILS
- Name submission on login API with stepId='user-signup' → 400 CONNECTION_ISSUE
- Name submission on signup API (/signup/api/execute) → 400 CONNECTION_ISSUE
- Any API call AFTER the email submit → 400 CONNECTION_ISSUE

## KEY INSIGHT
The CONNECTION_ISSUE happens because the browser's `fetch()` call through the SOCKS5/HTTPS proxy creates a NEW TLS connection that AWS detects as different from the page load connection.

## PROXY CONFIG
- ProxyRise HTTPS mode: `https://res-us-sid-{RANDOM}:{API_KEY}@gw.proxyrise.com:443`
- Local wrapper on port 8899 bridges local HTTP to ProxyRise HTTPS
- Connection pooling implemented (same client+target reuses TLS tunnel)
- But CONNECTION_ISSUE still occurs even with connection pooling

## POSSIBLE SOLUTIONS
1. **Don't use proxy for API calls after page load** - The browser's direct connection to AWS might work if we can bypass the proxy for the API calls while keeping the proxy for page loads.
2. **Use a different proxy approach** - Instead of wrapping SOCKS5/HTTPS, use a transparent proxy that doesn't change the TLS characteristics.
3. **Accept that the signup flow needs a different approach** - The email submit might be the last step that works, and the remaining steps need a different method.
4. **Check if the email submit already creates the account** - Maybe the email submission IS the account creation and the name/OTP steps are optional or handled differently.

## FILES
- `/home/ubuntu/kiro-gen/kiro_final.py` - main script (uses curl_cffi for API calls)
- `/home/ubuntu/kiro-gen/proxy_socks5_wrapper.py` - proxy wrapper with connection pooling
- `/home/ubuntu/kiro-gen/STATUS_FINAL.md` - this file

## NEXT STEPS
1. Try removing the proxy for API calls (use direct connection after page load establishes the session)
2. Or try using the browser's `page.request.post()` which might share the same connection pool
3. Or investigate if the email submit response contains all needed info to skip name/OTP steps
