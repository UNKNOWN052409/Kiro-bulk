# Task Notes v24 - Kiro Token Endpoint

## Key Discovery
The Kiro app uses its own auth server:
- Token URL: `https://prod.us-east-1.auth.desktop.kiro.dev/oauth/token`
- Auth URL: `https://prod.us-east-1.auth.desktop.kiro.dev`
- Refresh URL: `https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken`
- Social Refresh URL: `https://prod.us-east-1.auth.desktop.kiro.dev/refreshToken`
- Auth Methods: ["builder-id", "idc", "google", "github", "import"]

## Token Endpoint Test Results
- `https://prod.us-east-1.auth.desktop.kiro.dev/oauth/token` returns HTTP 400 with empty message
- Tried device_code grant with client_id, client_secret, code_verifier - all return 400
- The 400 might mean the endpoint expects different parameters or a different grant type

## Panel Import API
- POST `/api/oauth/kiro/import` with body `{"refreshToken": "<token>"}`
- Returns `{"error":"Token refresh failed: {\"message\":\"Bad credentials\"}"}` for invalid tokens
- This means the panel validates the token by trying to refresh it

## Device Code Response
The panel's `/api/oauth/kiro/device-code` returns:
- device_code, user_code, verification_uri, verification_uri_complete
- expires_in: 600, interval: 1
- _clientId, _clientSecret (JWT), _region, _authMethod, _startUrl
- codeVerifier

## What We Know Works
1. Account creation (run_bot_patched.py)
2. Device auth flow (email → password → OTP → Confirm → Allow → "Request approved")
3. Panel login
4. Panel device code API
5. Panel import API (validates tokens)

## What's Missing
- Getting a valid refresh token to import to the panel
- The AWS OIDC endpoint returns 403 (AccessDenied)
- The Kiro auth endpoint returns 400 (Bad Request)

## Next Steps
1. Try the Kiro auth endpoint with different parameters (maybe the grant_type format is different)
2. Try using the social-authorize or social-exchange endpoints
3. Try to get the refresh token from the Kiro app after account creation (network interception)
4. Check if the panel's auto-import works (it might detect tokens from the system)
