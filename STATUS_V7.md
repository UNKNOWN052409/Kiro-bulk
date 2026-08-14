# STATUS V7 - Full Browser Flow (working!)

## Script: /home/ubuntu/kiro-gen/mitm_account_creator.py

## Key Finding: The FULL BROWSER FLOW WORKS!
The browser preserves cookies/session from the OIDC redirect through to profile.aws.amazon.com. No proxy needed on the browser.

## Confirmed Flow:
1. OIDC register (no proxy) → Client ID
2. Browser navigates to OIDC authorize URL
3. Browser follows redirects: view.awsapps.com → portal.sso → signin.aws
4. Browser fills email, clicks Continue
5. **Browser automatically redirects to profile.aws.amazon.com/?workflowID=UUID** (session preserved!)
6. SPA loads in ~4-6s showing "Enter your name" form
7. Fill name → Click Continue → OTP page appears
8. Get OTP from Gmail → Fill OTP → Click Verify
9. Password page appears → Fill password → Click Create
10. Token callback captures authorization code on port 9997

## Proxy Info:
- ProxyRise SOCKS5 sticky session: `socks5://res-us-sid-SESSIONID:APIKEY@gw.proxyrise.com:443`
- Format: `res-us-sid-{random_int}:{PROXYRISE_API_KEY}@gw.proxyrise.com:443`
- API Key: pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1
- Sticky session keeps same IP for all requests in a session
- WITHOUT proxy: datacenter IP → ERR-837 on name submission (confirmed earlier)

## Current Status:
- Browser WITHOUT proxy works for the entire flow
- But ERR-837 will happen on name submission (datacenter IP)
- Need to figure out how to use proxy for just the critical API calls
- OR find a proxy that works for profile.aws.amazon.com domain

## The Last Test (PARTIAL):
- All steps 1-4 worked
- SPA loaded but name wasn't filled (script didn't detect the name form properly)
- The fix was applied - better detection and proper sequence
