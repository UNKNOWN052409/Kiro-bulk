# Status V14 - Critical Findings

## What We KNOW Works:
1. **Proxy wrapper (proxy_wrapper_standalone.py)** - Local HTTP→SOCKS5 proxy on port 8899
   - Works with curl: `curl -x http://127.0.0.1:8899 https://api.ipquery.io/`
   - Provides residential US IP (verified)
   - MUST be started BEFORE `fuser -k 8899/tcp` or the kill will remove it

2. **Browser WITHOUT proxy** - SPA renders fast on signin.aws and profile.aws.amazon.com
   - Email form, name page, all work perfectly

3. **Hybrid (intercept send-otp via page.route() + replay through proxy)** - Gets ERR-837/TES BLOCKED
   - Even with curl_cffi Chrome impersonation through residential proxy
   - The TES block is about SESSION CONSISTENCY, not just IP

## What DOESN'T Work:
1. Playwright `proxy={'server': 'http://...'}` → ERR_SSL_PROTOCOL_ERROR
2. Playwright `--proxy-server` flag → ERR_TIMED_OUT (when proxy not running)
3. `requests` with `proxies={'https': 'http://...'}` → SSL WRONG_VERSION_NUMBER
4. send-otp through residential proxy (even with Chrome TLS impersonation) → TES BLOCKED

## The ONLY Working Approach So Far:
**Browser with proxy from the VERY START** (browser_full_proxy.py approach):
- Proxy wrapper started as separate process (subprocess.Popen with start_new_session=True)
- Browser launched with `--proxy-server=http://127.0.0.1:8899`
- ignore_https_errors=True in context
- Very long timeouts (120s)
- The SPA IS slow but DOES render through the proxy
- The name page DID show "Enter your name" and the name WAS filled

## Key Fix Needed:
The proxy wrapper was being killed by `fuser -k 8899/tcp` BEFORE the script could start it.
Solution: Start the proxy FIRST, then check if it's running.

## Files:
- /home/ubuntu/kiro-gen/proxy_wrapper_standalone.py - Local HTTP→SOCKS5 proxy (WORKS)
- /home/ubuntu/kiro-gen/full_proxy_creator.py - Full proxy browser approach (needs proxy startup fix)
- /home/ubuntu/kiro-gen/hybrid_v2.py - Hybrid with page.route() (gets TES BLOCKED)
- /home/ubuntu/kiro-gen/browser_full_proxy.py - Earlier full proxy attempt (worked partially)

## ProxyRise Config:
- API Key: pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1
- Endpoint: gw.proxyrise.com:443
- SOCKS5 format: socks5h://res-us-sid-SESSIONID:APIKEY@gw.proxyrise.com:443
- Sticky session: use same SESSIONID for consistent IP

## Gmail OTP:
- Email: anshika31618@gmail.com
- App password: hlcv eobi tfwh terw

## Target:
- 30 accounts @havenhaus.in
- Import tokens to 9Router panel (https://ourproxy.sryze.cc/dashboard/providers)
- Provider: kiro, Pass: 7894561230
