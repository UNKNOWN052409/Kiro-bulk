# Kiro Account Creator - Status V30

## BREAKTHROUGH: Email step works with SIGNUP action!

## Key Findings
- Email step: MUST use `action_id='SIGNUP'` (not SUBMIT) with `{'input_type': 'UserRequestInput', 'identity': email_addr}` + fingerprint
- After email success, response has:
  - `stepId: "user-signup"`
  - `redirect.url: "https://us-east-1.signin.aws/platform/d-9067642ac7/signup?workflowStateHandle=..."`
- Need to navigate browser to redirect URL to get new workflow state
- Then name step uses the signup endpoint base URL

## Architecture (kiro_final.py)
1. OIDC register: curl_cffi + HTTP proxy (8899)
2. Browser navigate via SOCKS5 bridge (10800) → get initial workflowStateHandle
3. Init call: fetch on same origin with stepId='', empty inputs (just fingerprint)
4. Load email form: fetch with stepId from init, just fingerprint
5. Submit email: fetch with SIGNUP action + UserRequestInput(identity=email)
6. Navigate to redirect URL (signup page)
7. Submit name: fetch on signup base with TextInput(verifiedUserName)
8. Send OTP: fetch with just fingerprint
9. Verify OTP: fetch with TextInput(key='otp')
10. Set password: fetch with PasswordRequestInput
11. Token exchange: curl_cffi + HTTP proxy

## Current Issue: SOCKS5 bridge dies after browser navigation
- Browser makes many concurrent connections, bridge can't handle them all
- Bridge threads for forward() data relay die silently
- Need to make bridge more robust with better error handling

## Fix Applied to socks5_bridge.py
- Added non-blocking thread management (no join, daemon threads)
- Added traceback import
- Added time import

## Proxies
- HTTP: port 8899 (proxy_wrapper_standalone.py) - used by curl_cffi
- SOCKS5: port 10800 (socks5_bridge.py) - used by Playwright browser
- Both need `--session res-us`

## Restart commands:
```bash
kill $(ps aux | grep -E "socks5_bridge|proxy_wrapper" | grep -v grep | awk '{print $2}') 2>/dev/null
cd /home/ubuntu/kiro-gen
nohup python3 socks5_bridge.py --port 10800 --session res-us > /tmp/sb.log 2>&1 &
nohup python3 proxy_wrapper_standalone.py --port 8899 --session res-us > /tmp/pw.log 2>&1 &
sleep 3
```

## Still to fix:
1. SOCKS5 bridge stability (make it handle many concurrent connections)
2. Name step after navigating to signup URL (need to verify the correct stepId and base URL)
3. OTP + Password + Token exchange steps
4. Then scale to 30 accounts
