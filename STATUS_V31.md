# Kiro Account Creator - Status V31

## KEY DISCOVERY: ProxyRise HTTPS proxy mode gives clean US residential IPs

### The Problem
- `res-us` via SOCKS5 → gives US IPs but some are datacenter
- `res-us` via plain HTTP CONNECT → 400 error (Cloudflare blocks it)
- `res-us` via HTTPS proxy mode (TLS to proxy) → **clean US residential IPs (datacenter=false, risk=0)**

### Test results:
- `curl --proxy "https://res-us:APIKEY@gw.proxyrise.com:443" --proxy-insecure https://api.ipquery.io/?format=json`
  → IP: 107.199.147.188, AT&T, Indianapolis, US, residential, risk=0 ✓
- `curl -x "socks5h://res-us:APIKEY@gw.proxyrise.com:443" https://api.ipquery.io/?format=json`
  → IP: 104.203.153.251, US, but **datacenter=true** ✗

### Solution implemented:
- Rewrote `proxy_wrapper_standalone.py` (v3) to use HTTPS proxy mode to ProxyRise
- Browser uses HTTP proxy on port 8899 (wrapper handles HTTPS to ProxyRise internally)
- curl_cffi also uses HTTP proxy on 8899

### Current architecture (kiro_final.py):
1. OIDC register: curl_cffi + HTTP proxy 8899 (HTTPS to ProxyRise)
2. Browser navigate via HTTP proxy 8899 (HTTPS to ProxyRise) → get workflowStateHandle
3. Init call: page.evaluate() fetch with stepId='', fingerprint only
4. Load email form: fetch with stepId from init, fingerprint only
5. Submit email: fetch with SIGNUP action + UserRequestInput(identity=email)
6. Navigate to redirect URL (signup page)
7. Submit name: fetch on signup base with TextInput(verifiedUserName)
8. Send OTP: fetch with fingerprint only
9. Verify OTP: fetch with TextInput(key='otp')
10. Set password: fetch with PasswordRequestInput
11. Token exchange: curl_cffi + HTTP proxy 8899

### Email step WORKS:
- action_id='SIGNUP' (not SUBMIT)
- inputs: [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': fp}, {'input_type': 'UserRequestInput', 'identity': email}]
- Response: stepId='user-signup', redirect.url with new workflowStateHandle on /signup endpoint

### Files:
- kiro_final.py: main script (browser nav + fetch API calls)
- proxy_wrapper_standalone.py: v3 - HTTP local proxy → HTTPS to ProxyRise
- socks5_bridge.py: v2 - SOCKS5 bridge (less stable, not needed now)

### To run:
```bash
cd /home/ubuntu/kiro-gen
pkill -f proxy_wrapper_standalone
nohup python3 proxy_wrapper_standalone.py --port 8899 --session res-us > /tmp/pw.log 2>&1 &
sleep 3
python3 kiro_final.py 2>&1
```

### Remaining steps:
1. Test the name step (after navigating to /signup with new workflow state)
2. Add OTP extraction from Gmail (anshika31618@gmail.com)
3. Add OTP submission step
4. Add password setting step
5. Add token exchange
6. Scale to 30 accounts
7. Import to 9Router panel (https://ourproxy.sryze.cc/dashboard/providers, pass: 7894561230)
