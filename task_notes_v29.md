# Task Notes v29 - Full Flow Works But Panel Poll Fails

## What Works
1. Device code from panel: GET /api/oauth/kiro/device-code ✅
2. Browser device auth: email → password → OTP → Allow ✅
3. "Request approved" confirmed ✅
4. OTP extraction from Spam (body_html, not body) ✅

## What Doesn't Work
- POST /api/oauth/kiro/poll with {"deviceCode": "..."} returns "invalid_client"

## The Problem
The panel's poll endpoint uses its own client credentials to exchange the device code for tokens at the AWS endpoint. The "invalid_client" error means AWS is rejecting the panel's client credentials.

## Possible Solutions
1. The panel might need the device auth to be initiated from its own UI (not externally)
2. The panel's client might be configured for a different region/endpoint
3. We need to do the token exchange ourselves using the device code response

## Device Code Response Structure
```json
{
  "device_code": "...",
  "user_code": "XXXX-XXXX",
  "verification_uri": "https://view.awsapps.com/start/#/device?user_code=...",
  "verification_uri_complete": "https://view.awsapps.com/start/#/device?user_code=...",
  "expires_in": 600,
  "interval": 5,
  "_clientId": "...",
  "_clientSecret": "...",
  "_region": "us-east-1",
  "codeVerifier": "..."
}
```

## Token Endpoint to Try
The Kiro auth server token URL (from panel JS):
`https://prod.us-east-1.auth.desktop.kiro.dev/oauth/token`

Parameters:
- grant_type: urn:ietf:params:oauth:grant-type:device_code
- device_code: <device_code>
- client_id: <_clientId>
- client_secret: <_clientSecret>

Or the AWS OIDC endpoint:
`https://oidc.us-east-1.amazonaws.com/oauth2/token`

## Panel Import API
POST /api/oauth/kiro/import with {"refreshToken": "..."}
This is the endpoint we need to hit once we have the refresh token.
