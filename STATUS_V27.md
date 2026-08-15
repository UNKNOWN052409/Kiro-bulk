# Kiro Account Creator - Status V27

## Key Findings

### TES (Threat Evaluation Service) Blocking
- TES blocks Playwright/undetected-chromedriver browsers on the Kiro-specific signin page (us-east-1.signin.aws)
- TES does NOT block curl_cffi with Chrome TLS impersonation through residential proxy
- TES blocks regardless of IP (tested with residential proxy, direct VPS, different emails/domains)

### API State Machine Format (from api_only_creator.py analysis)
The correct payload format for /api/execute:
```json
{
  "stepId": "<previous_response_stepId>",
  "workflowStateHandle": "<previous_response_workflowStateHandle>",
  "inputs": [
    {"input_type": "FingerPrintRequestInput", "fingerPrint": {...}},
    {"input_type": "TextInput", "key": "identity", "value": "email"},
    {"input_type": "UserRequestInput", "username": "email"},
    {"input_type": "PasswordRequestInput", "password": "..."},
    {"input_type": "TextInput", "key": "verifiedUserName", "value": "name"},
    {"input_type": "TextInput", "key": "otp", "value": "123456"}
  ],
  "visitorId": "<uuid>",
  "requestId": "<uuid>"
}
```

State machine flow:
1. Initial POST: stepId="" + random workflowStateHandle (new UUID) → gets real ws + step
2. POST with step from response (fingerprint only) → loads form
3. POST with step + inputs → submits form
4. Response contains redirect to profile.aws.amazon.com with workflowID
5. On profile.aws.amazon.com: repeat state machine for name → OTP → password

### Proxy Configuration
- SOCKS5 bridge: port 10800 (for Playwright browser)
- HTTP wrapper: port 8899 (for curl_cffi)
- Both use session 'res-us' from ProxyRise
- SOCKS5 bridge works reliably with Playwright
- HTTP wrapper keeps dying/timing out - needs restart

### What Works
- Browser + SOCKS5 proxy → gets clean residential IP, navigates to Kiro login page
- curl_cffi + HTTP proxy → gets clean residential IP, makes API calls without TES block
- OIDC client registration works
- Email submission via browser works (SPA handles it internally)
- curl_cffi POST to /api/execute returns 200 (not TES-blocked) with correct Chrome impersonation

### What Doesn't Work
- Browser API calls (SPA internal requests) → TES blocks them with ERR-837
- curl_cffi with wrong payload format → 400 errors
- HTTP proxy wrapper → keeps timing out after a few requests

### Current Approach (kiro_final.py v3)
- Uses Playwright browser for full UI automation with SOCKS5 proxy
- Types human-like (character by character with delays)
- Uses keyboard Enter to submit forms
- Intercepts API calls for debugging
- This is the simplest approach - if TES blocks it, we need to find another way

### TODO
- If browser approach still gets TES-blocked, try:
  1. Using curl_cffi for ALL API calls with correct state machine format
  2. Need to figure out how to get workflow state without browser consuming it
  3. Or use browser request interception to capture exact SPA API calls and replay with curl_cffi
