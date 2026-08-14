# STATUS V6

## Key findings:
1. Steps 0-3 (OIDC register, redirect chain, email submit, signup) ALL WORK via API with proxy
2. Without proxy on browser: profile.aws.amazon.com SPA DOES load (no "can't reach" error)
3. But the SPA immediately navigates (execution context destroyed) - the SPA loads and redirects
4. The `page.evaluate('document.body.innerText')` fails because the page is still loading/navigating

## Fix needed:
- In the SPA wait loop, wrap `page.evaluate()` in try/except to handle "Execution context was destroyed"
- The SPA loads and redirects quickly (within ~2s), so the first evaluate might fail but subsequent ones should work
- Or wait for a specific element/networkidle before evaluating

## Script: mitm_account_creator.py
- Line ~368: body_text = page.evaluate('document.body.innerText') - needs try/except
- The browser has NO proxy (profile.aws.amazon.com doesn't work through proxy)
- All API calls (steps 0-3) use sticky session proxy (res-us-sid-SESSIONID)

## What happens after SPA loads:
- /api/start is called from browser context
- Then name form is filled
- Then OTP is submitted
- Then password is submitted
- Token callback waits on port 9997

## ERR-837 concern:
- Without proxy, the browser uses datacenter IP → might get ERR-837 on send-otp
- But earlier test (test_full_flow_spa.py) showed ERR-837 happens on name submission
- Need to test if sticky proxy IP (same IP for all requests) fixes this
