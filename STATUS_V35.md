# Kiro Account Creator - Status V35

## Key Discovery
The ProxyRise HTTPS proxy mode works with `--proxy-insecure` flag (self-signed cert). The correct auth format is:
- Username: `res-us-sid-{RANDOM}` (just the session ID, NOT with API key appended)
- Password: `{API_KEY}`

The HTTPS proxy mode with sticky session gives the SAME IP across all requests.

## Proxy Wrapper Update
The `proxy_socks5_wrapper.py` has been updated to use HTTPS mode (TLS to gateway, skip cert verification, CONNECT with Proxy-Authorization). The auth was fixed: USERNAME=SESSION only, PASSWORD=API_KEY.

## Current State of kiro_final.py
- Steps 1-4 work perfectly (OIDC register, browser navigate, init, email form, email submit)
- Step 5 (name submission on signup API at `/signup/api/execute`) consistently returns 400 CONNECTION_ISSUE
- The CONNECTION_ISSUE error means the TLS connection for the API call doesn't match the page load connection
- The fix should be the HTTPS proxy mode which maintains consistent TLS characteristics

## LATEST FINDINGS (updated)
The login API with stepId='user-signup' also returns 400 for name submission.
The signup API at /signup/api/execute also returns 400.
The CONNECTION_ISSUE error is the root cause - AWS TES detects different TLS connections.

The key issue: the `page.evaluate()` fetch creates a NEW connection for each API call.
The browser's page load uses one connection, and the fetch uses another.
The ProxyRise HTTPS proxy gives the same IP but the TCP/TLS connection is different.

SOLUTION NEEDED: We need to make the fetch use the SAME underlying TCP connection as the page load.
This is what a real browser does - it reuses connections (HTTP/2 multiplexing or keep-alive).
The ProxyRise gateway might not support connection reuse for the browser's connections.

ALTERNATIVE: Use curl_cffi with the SAME TLS session for all requests. curl_cffi can maintain
a persistent connection pool. If we use curl_cffi with the ProxyRise HTTPS proxy (--proxy-insecure),
it should maintain the same TLS characteristics across requests.

## Next Steps
1. Restart the HTTPS wrapper and verify IP consistency
2. Run kiro_final.py with the HTTPS wrapper
3. If CONNECTION_ISSUE persists, the issue is that each fetch creates a NEW TLS connection to the target
4. The solution might be to keep the browser on the LOGIN page and make all API calls from there (including signup API calls)

## Files
- `/home/ubuntu/kiro-gen/kiro_final.py` - main script
- `/home/ubuntu/kiro-gen/proxy_socks5_wrapper.py` - HTTPS proxy wrapper (updated)
- `/home/ubuntu/kiro-gen/STATUS_V35.md` - this file

## ProxyRise Details
- API Key: `pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1`
- Gateway: `gw.proxyrise.com:443`
- HTTPS mode: `https://res-us-sid-{ID}:{API_KEY}@gw.proxyrise.com:443`
- Sticky session: same `res-us-sid-{ID}` gives same IP
- Requires `--proxy-insecure` (self-signed cert)
