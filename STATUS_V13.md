# Status V13 - Proxy Connection Issues

## Key Findings:

### What Works:
- `curl -x http://127.0.0.1:8899 https://...` works perfectly (CONNECT tunneling)
- Proxy wrapper provides residential US IP (verified with ipquery.io)
- Browser WITHOUT proxy: SPA renders fine, email/name submission works
- The complete flow WITHOUT proxy: OIDC → signin → email → profile.aws.amazon.com → name → ERR-837 on send-otp

### What DOESN'T Work:
1. Playwright `proxy={'server': 'http://...'}` → ERR_SSL_PROTOCOL_ERROR
2. Playwright `--proxy-server=http://...` flag → ERR_TIMED_OUT (proxy not running at that point)
3. `requests` with `proxies={'https': 'http://127.0.0.1:8899'}` → SSL WRONG_VERSION_NUMBER
4. send-otp through residential proxy (even with curl_cffi Chrome impersonation) → still ERR-837/TES BLOCKED

### Root Cause Analysis:
- The TES block is NOT about IP alone. Even residential IP gets blocked.
- The TES block is about SESSION CONSISTENCY. The cookie/token was issued from datacenter IP, so requests from residential IP with that cookie get blocked.
- OR the fingerprint in browserData contains datacenter IP info (WebRTC leak)
- OR the TLS fingerprint from non-browser clients doesn't match

### Current Best Approach:
The ONLY working solution so far: browser WITHOUT proxy for everything EXCEPT profile.aws.amazon.com.
But profile.aws.amazon.com blocks everything from datacenter IP (ERR-837).

### Files:
- full_proxy_creator.py - Full proxy approach (broken - proxy connection issues)
- final_creator.py - Hybrid with curl_cffi (broken - TES still blocks)
- proxy_wrapper_standalone.py - Local HTTP→SOCKS5 proxy (works with curl)
- STATUS_V12.md - Previous findings

### Next Steps to Try:
1. Fix the proxy wrapper to handle both CONNECT and plain HTTP
2. OR use curl_cffi with SOCKS5 proxy directly (not through local wrapper)
3. OR accept that we need the browser on the proxy and fix the SSL issue
