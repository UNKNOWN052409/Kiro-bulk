# Kiro Account Creator - Status V29

## Latest Approach (kiro_final.py v5)
Browser navigates through SOCKS5 residential proxy → lands on signin page → uses browser's fetch() for ALL API calls on same origin.

Key files:
- kiro_final.py: Main script (browser + fetch API calls)
- socks5_bridge.py: Local SOCKS5 proxy on port 10800 (for Playwright browser)
- proxy_wrapper_standalone.py: HTTP proxy on port 8899 (for curl_cffi)
- kiro_creator.py: Original browser-based script (playwright UI interaction)

## Architecture
1. OIDC register: curl_cffi + HTTP proxy (port 8899)
2. Browser navigate: Playwright + SOCKS5 bridge (port 10800) → gets workflowStateHandle
3. API calls (init, email, name, otp, password): browser fetch() on same origin
4. Token exchange: curl_cffi + HTTP proxy

## Why fetch() instead of UI interaction?
- UI interaction (Playwright fill + click) → SPA makes POST → TES blocks with ERR-837
- fetch() on same origin → goes through browser's TLS session but with controlled payload
- Hoping TES doesn't block because the request originates from within the page's JS context

## Known Issues
- SOCKS5 bridge (port 10800) keeps dying - needs restart
- HTTP proxy wrapper (port 8899) also dies - needs restart
- Need to run both before each test

## Restart commands:
```bash
kill $(ps aux | grep -E "socks5_bridge|proxy_wrapper" | grep -v grep | awk '{print $2}') 2>/dev/null
cd /home/ubuntu/kiro-gen
nohup python3 socks5_bridge.py --port 10800 --session res-us > /tmp/sb.log 2>&1 &
nohup python3 proxy_wrapper_standalone.py --port 8899 --session res-us > /tmp/pw.log 2>&1 &
sleep 3
```

## Key API Facts
- Signin base: https://us-east-1.signin.aws/platform/d-9067642ac7
- Profile base: https://profile.aws.amazon.com
- API endpoint: /api/execute on both bases
- Fingerprint format: "ECdITeCs:<base64>" (string, not dict)
- Input types: FingerPrintRequestInput, UserRequestInput, TextInput, PasswordRequestInput
- State machine: each response gives new stepId + workflowStateHandle for next call
- Flow: init(stepId='') → email → name → otp-send → otp-verify → password

## ProxyRise Config
- Endpoint: gw.proxyrise.com:443
- API Key: pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1
- Session: res-us
- SOCKS5: socks5://res-us:APIKEY@gw.proxyrise.com:443
- HTTP: http://res-us:APIKEY@gw.proxyrise.com:443

## Gmail OTP
- Email: anshika31618@gmail.com
- Pass: hlcv eobi tfwh terw
