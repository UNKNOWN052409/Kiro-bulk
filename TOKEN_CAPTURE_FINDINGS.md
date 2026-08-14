# Token Capture - Critical Findings (Aug 13, 2026 - Updated)

## Root Cause of "InvalidGrantException: Device code already redeemed"
The AWS SSO portal SPA calls `associate_token` when the user clicks "Allow". This endpoint:
1. Generates the OIDC refresh/access tokens server-side
2. Marks the device code as "redeemed"
3. Returns an EMPTY response body (status 200, mimeType=application/json)

Our subsequent `create_token` call always fails because the SPA already redeemed the device code.
- Even with 50ms poll head start and 10ms intervals, the SPA wins (0.91s for 3 attempts)
- Blocking `associate_token` via CDP prevents token generation entirely
- The `associate_token` response body is EMPTY - no token is returned

## What We CAN Capture
1. **SSO Session Token** from `POST /session/device` → returns `{"token": "eyJ..."}` (JWE format, ~1472 bytes)
   - This is the SSO portal session token (DataPlaneSession, origin: Peregrine)
   - Can be used with `x-amz-sso_authn` header for SSO portal API calls
   - Gets "ForbiddenException: User not authorized" for list_accounts (new accounts have no IAM roles)

2. **deviceContextId** from success callback URL → JWT with `{"region":"us-east-1","userCode":"..."}`
   - NOT the OIDC refresh token

## What DOESN'T Work (All Tried)
- `create_token` after Allow click ❌ (always "already redeemed" - SPA wins race)
- Ultra-aggressive polling (10ms intervals, 50ms head start) ❌
- CDP block `associate_token` ❌ (prevents token generation)
- CDP capture `associate_token` response body ❌ (empty)
- localStorage/sessionStorage ❌ (no tokens stored)
- IndexedDB ❌ (no databases)
- Window state variables ❌ (nothing token-related)
- Browser fetch to OIDC endpoint ❌ (400/403)
- Authorization code flow with PKCE ❌ (OAuth2 authorize endpoint doesn't exist on SSO portal - "Page not found")
- Federation credentials API ❌ (401 "Session token not found or invalid")

## Key Insight: Authorization Code Flow Not Available
The AWS SSO portal does NOT expose an OAuth2 authorization endpoint. The only URL formats tested:
- `https://view.awsapps.com/start/#/oauth2/authorize` → "Page not found"
- `https://view.awsapps.com/oauth2/authorize` → XML error
- `https://portal.sso.us-east-1.amazonaws.com/oauth2/authorize` → "Could not find resource"

The `register_client` API DOES support `redirectUris` and `grantTypes=['authorization_code']`, but the web portal doesn't have a corresponding authorization endpoint.

## Panel Requirements
- 9Router panel API: `POST /api/oauth/kiro/import`
- Body: `{"refreshToken": "...", "region": "us-east-1", "authMethod": "builder-id", "startUrl": "https://view.awsapps.com/start", "name": "email"}`
- Panel needs OIDC `refreshToken` from `create_token`
- Panel is currently DOWN (Cloudflare 530)

## What Works
- Full browser flow (Email → Name → OTP → Password → Confirm → Allow) ✅
- OTP extraction via Gmail IMAP (<1s) ✅
- SSO session token capture via `session/device` ✅
- Account creation (20+ accounts already in kiro_accounts.csv) ✅

## Remaining Options to Try
1. Use the SSO session token as the "refreshToken" for the panel (might work)
2. Check if the Kiro CLI source code reveals a different approach
3. Try the `session/device` token with the panel's import API
4. Accept that OIDC refresh token can't be captured and use SSO session token instead
