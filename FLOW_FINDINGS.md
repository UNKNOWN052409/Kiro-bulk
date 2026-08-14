# AWS/Kiro Account Creation Flow - Key Findings

## Complete Redirect Chain
1. `oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id={client_id}&redirect_uri=http://127.0.0.1:9997/oauth/callback&scopes=codewhisperer:completions%20codewhisperer:analysis%20codewhisperer:conversations%20codewhisperer:transformations%20codewhisperer:taskassist&state={state}&code_challenge={code_challenge}&code_challenge_method=S256`
2. → 302 → `view.awsapps.com/start/?callback_url=https://oidc.us-east-1.amazonaws.com/authentication_result&orchestrator_id={long_base64_string}`
3. → JS calls `GET https://portal.sso.us-east-1.amazonaws.com/login?directory_id=view&redirect_url={start_url}`
   - Returns: `{"redirectUrl": "https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={uuid}", "csrfToken": "{number}"}`
4. → Follow redirectUrl to signin.aws (React SPA)

## OIDC Client Registration
```python
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"],
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9997/oauth/callback"],
    "issuerUrl": "https://view.awsapps.com/start"
}
# POST to https://oidc.us-east-1.amazonaws.com/client/register
# Returns: {"clientId": "..."}
```

## PKCE
```python
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
```

## Signin Page Structure
- URL: `https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={uuid}`
- It's a React SPA (1.5KB HTML + 3.7MB JS bundle at `/assets/js/app.js`)
- The JS has an API endpoint: `/api/execute` (the main API for all operations)
- Cookies needed: `loginCsrfToken` (set from portal.sso response), `platform-ubid` (from signin.aws)

## Key API Endpoint
- `/api/execute` on `us-east-1.signin.aws` - this is the main API for the signin flow
- All form submissions (email, name, OTP, password) go through this endpoint

## ProxyRise Config
- API Key: `pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1`
- Endpoint: `gw.proxyrise.com:443`
- SOCKS5 format: `socks5://res-us-sid-SESSIONID:APIKEY@gw.proxyrise.com:443`
- Sticky session: `res-us-sid-{random_8_digit}`
- Residential US IPs confirmed working (risk score 0, not datacenter/VPN)
- Verified IPs: 72.218.2.42 (Cox, Norfolk VA), 184.52.126.236 (Hughes, Portland OR)

## Profile API (profile.aws.amazon.com)
- `GET /` → 483 byte HTML SPA shell (works through proxy)
- `POST /api/get-config` → `{}` → returns features JSON (works through proxy)
- `POST /api/get-app-context` → `{"workflowID":"{uuid}"}` → 404 if invalid session
- `POST /api/start` → needs browserData with fingerprint
- `POST /api/send-otp` → name data
- `POST /api/verify-otp` → OTP code
- `POST /api/set-password` → password

## Gmail OTP
- User: anshika31618@gmail.com
- App Password: hlcveobitfwh terw (no spaces: hlcveobitfwh terw)
- Extract 6-digit OTP from email body

## 9Router Panel
- URL: https://ourproxy.sryze.cc/dashboard/providers
- Provider: kiro
- Pass: 7894561230

## Target
- 30 accounts with @havenhaus.in domain
- Each with unique ProxyRise sticky session
- Rust container with 0.1 CPU limit (later phase)
