# Status V10 - Key Findings

## Current Approach: hybrid_creator.py (browser WITHOUT proxy)
- Browser without proxy for SPA rendering (fast on datacenter IP)
- JS-based input filling (handles shadow DOM)
- No proxy interception yet (testing if ERR-837 happens on signin.aws execute API)

## Key Findings So Far:
1. SPA renders fine WITHOUT proxy (datacenter IP)
2. SPA is TOO SLOW through residential proxy (never renders name form)
3. The execute API is on `us-east-1.signin.aws` (NOT profile.aws.amazon.com)
4. ERR-837 was on profile.aws.amazon.com - need to test if it also applies to signin.aws
5. Earlier test: name submission through datacenter DID work (SPA showed name step)
6. The flow: email → ENTITY_DOES_NOT_EXIST → user-signup → start → name → OTP → password → token

## AWS Execute API Format (signin.aws)
- POST to `/platform/d-9067642ac7/api/execute`
- Body: {"stepId":"...", "workflowStateHandle":"...", "actionId":"SUBMIT", "inputs":[...], "visitorId":"...", "requestId":"..."}
- Steps: "" → "start" → "get-identity-user" SUBMIT → (ENTITY_DOES_NOT_EXIST) → SIGNUP → "" → "user-signup" → start → name → OTP → password → token

## ProxyRise Config
- API Key: pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1
- SOCKS5: socks5://res-us-sid-{SID}:APIKEY@gw.proxyrise.com:443
- Local wrapper: proxy_wrapper_standalone.py (listens 127.0.0.1:8899, forwards to SOCKS5)
- Sticky sessions work: res-us-sid-{random_number}

## Gmail OTP
- User: anshika31618@gmail.com
- App Password: hlcveobitfterw

## Files
- hybrid_creator.py - NEW: browser without proxy, JS-based filling
- browser_full_proxy.py - OLD: browser with proxy (SPA too slow)
- proxy_wrapper_standalone.py - Working local HTTP-to-SOCKS5 proxy
- STATUS_V9.md - Previous findings

## Next: Run hybrid_creator.py and see if ERR-837 happens on signin.aws
