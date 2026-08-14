# Status V9 - Current Working Approach

## Key Findings (from latest runs)
1. **Browser without proxy** works for OIDC → signin → email submission (fast, SPA renders)
2. **Browser with proxy wrapper** (localhost:8899 → SOCKS5 ProxyRise): SPA is too slow/heavy to render, form never appears
3. **API calls through proxy** work for get-config/start but the SPA state machine needs the browser
4. **ERR-837** happens specifically on the name/OTP/password submission steps when using datacenter IP
5. The SPA content is inside React shadow DOM - `document.body.innerText` returns empty for later steps

## Working Flow (browser without proxy for initial steps)
- OIDC authorize → signin.aws (SPA renders fine on datacenter IP)
- Email fill + Continue → works
- After email submit: SPA auto-sends `get-identity-user` SUBMIT → `ENTITY_DOES_NOT_EXIST` → SIGNUP → `""` step → `user-signup` → redirects to signup URL
- Name step appears but SPA is slow through proxy

## Best Hybrid Strategy (recommended)
1. Browser WITHOUT proxy for OIDC → signin → email (SPA renders fine)
2. After email submitted, the SPA navigates to name step
3. The name step SPA is lightweight enough to render even through proxy
4. OR: use page.route() to intercept only the execute API POST calls and replay through proxy

## Files
- `/home/ubuntu/kiro-gen/browser_full_proxy.py` - Browser with full proxy (SPA too slow)
- `/home/ubuntu/kiro-gen/mitm_account_creator.py` - Original hybrid with page.route() interception
- `/home/ubuntu/kiro-gen/proxy_wrapper_standalone.py` - Working local HTTP-to-SOCKS5 proxy wrapper
- `/home/ubuntu/kiro-gen/FLOW_CORRECTED.md` - Complete flow documentation

## ProxyRise Config
- API Key: pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1
- SOCKS5: socks5://res-us-sid-{SID}:APIKEY@gw.proxyrise.com:443
- Local wrapper: proxy_wrapper_standalone.py (listens on 127.0.0.1:8899)
- Sticky sessions: res-us-sid-{random_number}

## Gmail OTP
- User: anshika31618@gmail.com
- App Password: hlcveobitfwh terw (no spaces)

## AWS Execute API
- POST https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute
- Steps: "" → "start" → "get-identity-user" SUBMIT → (ENTITY_DOES_NOT_EXIST) → SIGNUP → "" → "user-signup" → name → OTP → password → token redirect
- Body format: {"stepId":"...", "workflowStateHandle":"...", "actionId":"SUBMIT", "inputs":[...], "visitorId":"...", "requestId":"..."}
- Inputs include: UserRequestInput, FingerPrintRequestInput, ApplicationTypeRequestInput, UserEventRequestInput, NameRequestInput

## Next Steps
1. Fix the hybrid approach: browser no-proxy for signin, then page.route() to intercept execute API calls and replay through proxy
2. OR: use longer timeouts for the proxy-based browser to let SPA render
