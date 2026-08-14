# BREAKTHROUGH - Token Capture Solved! (Aug 13, 2026)

## The Solution: Authorization Code Flow with PKCE

The device code flow ALWAYS fails with "already redeemed" because the AWS SSO portal SPA calls `associate_token` which redeems the device code before our `create_token` can succeed.

The CORRECT approach (used by Kiro Desktop) is the Authorization Code Flow with PKCE:

### Key Details from kiro-account-manager source (hj01857655/kiro-account-manager on GitHub)

1. **OIDC Base URL**: `https://oidc.{region}.amazonaws.com` (NOT the SSO portal URL)
2. **Client Registration**: POST to `https://oidc.us-east-1.amazonaws.com/client/register` with JSON body:
   ```json
   {
     "clientName": "kiro-xxxx",
     "clientType": "public",
     "scopes": ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"],
     "grantTypes": ["authorization_code", "refresh_token"],
     "redirectUris": ["http://127.0.0.1:{port}/oauth/callback"],
     "issuerUrl": "https://view.awsapps.com/start"
   }
   ```
3. **Authorize URL**: `https://oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id=...&redirect_uri=...&scopes=...&state=...&code_challenge=...&code_challenge_method=S256`
4. **Token Exchange**: POST to `https://oidc.us-east-1.amazonaws.com/token` with JSON body:
   ```json
   {
     "clientId": "...",
     "clientSecret": "...",
     "grantType": "authorization_code",
     "code": "...",
     "codeVerifier": "...",
     "redirectUri": "..."
   }
   ```
5. **Token Response**: Returns `accessToken`, `refreshToken`, `idToken`, `expiresIn`, `tokenType`, `aws_sso_app_session_id`, `originSessionId`

### Why This Works
- The browser navigates to the OIDC authorize endpoint (not the SSO portal device page)
- After login and clicking Allow, the browser REDIRECTS to localhost with the authorization code
- We capture the code from the redirect URL
- We exchange the code for tokens - NO race condition because there's no SPA calling associate_token

### Verified Working
- Successfully captured refresh token (230 chars) for test account
- Token saved to /tmp/kiro_token_final.json
- Token response includes: accessToken, refreshToken, idToken, expiresIn, tokenType, aws_sso_app_session_id, originSessionId

### Current State
- 20 unique accounts already created in kiro_accounts.csv
- Need 10 more to reach 30
- Panel (ourproxy.sryze.cc) still DOWN (530 error)
- Browser has existing session logged in as "Test User"

### Files Created
- capture_token_v2.py - Single account token capture (working!)
- batch_create_and_capture.py - Batch create + capture (not yet tested)
- TOKEN_CAPTURE_FINDINGS.md - Detailed findings

### Important Notes
- The redirect URI MUST use loopback: `http://127.0.0.1:{port}/oauth/callback`
- The scopes are Kiro-specific (codewhisperer:*), NOT SSO scopes
- Grant types: authorization_code + refresh_token
- Client registration uses direct HTTP POST (NOT boto3 sso-oidc client)
- Token exchange uses JSON body (NOT form-encoded)
