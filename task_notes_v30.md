# Task Notes v30 - Token Exchange Blocked

## Current Status
- Device auth flow: WORKS (sign in → OTP → Allow → "Request approved")
- Token exchange: FAILS from all endpoints
  - Kiro auth server: 400 {"Message":null}
  - AWS OIDC: 403 AccessDenied
  - Panel poll: "invalid_client"

## Root Cause
The panel's server is the only one that can exchange device codes for tokens. It uses its own client credentials from an authorized IP. We cannot replicate this from outside.

## Alternative Approaches to Try
1. **Social flow** (Google/GitHub): `/api/oauth/kiro/social-authorize` → get auth URL → sign in → callback has code → `/api/oauth/kiro/social-exchange` → get refresh token → `/api/oauth/kiro/import`
2. **Panel UI device auth**: Navigate the panel's UI to find the "Add Account" mechanism that triggers the panel's own device auth flow
3. **Direct import API**: If we can get a refresh token from ANY source, the `/api/oauth/kiro/import` endpoint accepts it

## Social Flow Details
- social-authorize returns: {url, codeVerifier}
- The url redirects to Kiro auth server for Google/GitHub sign-in
- After sign-in, callback has `code` parameter
- social-exchange accepts: {code, codeVerifier, provider}
- Returns: {refreshToken, accessToken}

## Problem with Social Flow
- The redirect_uri is `kiro://kiro.kiroAgent/authenticate-success` (custom scheme)
- This won't work in a browser (no callback)
- Need to find a way to capture the code from the redirect

## Next Steps
Try the social flow with Google sign-in. Even though the redirect_uri is a custom scheme, the auth server might still return the code in the URL before redirecting.
