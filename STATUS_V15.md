# Status V15 - Hybrid Approach with Direct SOCKS5

## Key Findings:

### ProxyRise SOCKS5 Session Formats:
- `res-us` → US residential IPs (Charter, Frontier, AT&T) - NOT datacenter, NOT proxy
- `res-us-sid-XXXX` → Datacenter IPs (DigitalOcean, Cogent) - WRONG!
- `res-any` → Random residential (Chile, Ukraine, etc.)
- Each `res-us` connection gets a DIFFERENT IP (no sticky session without sid)

### Working Direct SOCKS5 Test:
```
curl -x "socks5://res-us:pgw-APIKEY@gw.proxyrise.com:443" https://api.ipquery.io/
```
Gives: Charter Communications, Frontier Communications, AT&T (all residential)

### Hybrid Approach (V4 - hybrid_v3.py):
1. Browser loads SPA directly (NO proxy) - FAST
2. page.route() intercepts API calls to signin.aws/profile.aws /api/execute
3. Replays through SOCKS5 proxy using curl_cffi with impersonate='chrome'
4. Returns proxied response to browser

### Issues Found:
- First API call (start): status=200 ✓
- Second API call (get-identity-user): status=400 ✗
- The 400 is because curl_cffi impersonate might be overriding headers
- OR the POST body is not being forwarded correctly

### What Works Without Proxy:
- SPA loads in <1 second (direct)
- Email form appears instantly
- Name page renders in 3 seconds
- All UI interactions work perfectly

### What Blocks:
- ERR-837 when API calls go through datacenter IP
- "It's not you, it's us" when API calls fail/mixed IPs

### Files:
- hybrid_v3.py - Current hybrid approach (direct SPA + proxied API calls)
- full_proxy_creator.py - Full proxy approach (too slow, SPA takes 5+ min)
- proxy_wrapper_standalone.py - HTTP-to-SOCKS5 wrapper (works but slow)

### Gmail OTP:
- Email: anshika31618@gmail.com
- App password: hlcv eobi tfwh terw

### 9Router Panel:
- URL: https://ourproxy.sryze.cc/dashboard/providers
- Provider: kiro, Pass: 7894561230

### Target:
- 30 accounts @havenhaus.in
- Import tokens to 9Router panel
