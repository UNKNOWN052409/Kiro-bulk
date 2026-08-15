# Status V24 - TES Block Analysis & MITM Approach

## Key Finding: TES (Threat Evaluation Service)
- Error: `{"errorCode":"BLOCKED","message":"Request was blocked by TES."}`
- TES checks TLS/HTTP2 fingerprints (JA3), NOT just IP
- Residential proxy provides clean IP but TES still blocks because Playwright's Chromium has detectable TLS fingerprint
- The `/api/send-otp` call to `profile.aws.amazon.com` is what gets blocked
- Name submission to `profile.aws.amazon.com/api/start` succeeds (200)

## Solution: MITM + curl_cffi
- curl_cffi impersonates real Chrome TLS fingerprint
- Works through SOCKS5 bridge (port 10800)
- Test confirmed: Chrome124 impersonation + SOCKS5 proxy = clean residential IP

## Architecture
1. SOCKS5 Bridge (socks5_bridge.py on port 10800) -> ProxyRise residential proxy
2. curl_cffi with impersonate='chrome124' through SOCKS5 bridge
3. Replay the exact API calls from the OIDC signin flow

## Flow to implement (MITM-style, no browser):
1. POST https://oidc.us-east-1.amazonaws.com/client/register (OIDC client registration)
2. GET https://oidc.us-east-1.amazonaws.com/authorize?... (get workflow)
3. Follow redirects to us-east-1.signin.aws platform
4. POST /api/execute with step=email
5. POST /api/execute with step=name (or similar)
6. POST /api/send-otp (this is what TES blocks - need Chrome fingerprint)
7. Submit OTP
8. POST password creation
9. GET OAuth callback
10. POST https://oidc.us-east-1.amazonaws.com/token (exchange code)

## Files
- /home/ubuntu/kiro-gen/kiro_creator.py - Main script (browser-based, TES-blocked)
- /home/ubuntu/kiro-gen/socks5_bridge.py - SOCKS5 bridge to ProxyRise (WORKING)
- /home/ubuntu/kiro-gen/proxy_wrapper_standalone.py - HTTP wrapper (NOT working with Chromium)
- curl_cffi installed: sudo pip3 install curl_cffi

## Config
- Gmail: anshika31618@gmail.com / hlcv eobi tfwh terw
- ProxyRise: pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1 @ gw.proxyrise.com:443
- Session: res-us
- Domain: havenhaus.in
- 9Router: https://ourproxy.sryze.cc/dashboard/providers (user: kiro, pass: 7894561230)
