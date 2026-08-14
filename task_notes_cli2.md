# Panel State Update

## Kilo Code Provider (NOT Kiro)
- Kilo Code is a separate OAuth provider (1 connection: rup44973@gmail.com - disabled)
- Has models like kc/anthropic/claude-sonnet, kc/google/gemini, kc/openai/gpt etc.
- This is NOT the Kiro provider

## Key Finding
The "kiro" custom provider at the top is DISABLED. We need to find the Kiro OAuth provider.
Looking at the earlier API response, the connections had "provider": "kiro" and "authType": "oauth".
This means there IS a Kiro OAuth provider somewhere on the panel.

The earlier screenshot showed OAuth providers but the page might not have scrolled properly.
Let me look for a "Kiro" entry in the OAuth section that we might have missed.

## Panel API Endpoints (confirmed working)
- POST /api/auth/login with {"password": "..."} - returns auth_token cookie
- POST /api/oauth/kiro/import with {"refreshToken": "..."} - needs valid AWS refresh token
- GET /api/connections (returns full connection data with clientSecret etc.)

## Kiro AI Provider Page (FOUND!)
- URL: /dashboard/providers/kiro
- Shows "Kiro AI" with **95 connections** (not 93 as previously thought)
- Has a Risk Notice about OAuth session not officially licensed
- Round Robin is ON (toggle enabled)
- Sticky: 100
- All connections show "disabled" status
- Format: "Account NN" with OAuth tag
- Need to scroll down to find the "Add" button (below the connections list)

## CRITICAL FLOW DISCOVERY
The actual AWS Builder ID sign-in flow for NEW accounts is:
1. Email → submit
2. "Enter your name" page → fill name → Continue
3. "Verify your email" page → OTP from Gmail → Continue
4. "Confirm and continue" (Authorization requested)
5. "Allow" (if shown)

**There is NO password page for new accounts!** The flow goes:
Name → Email Verification (OTP) → Confirm → Allow

The panel_add_ui.py script waits for a PASSWORD page after the name page,
but the actual flow goes to OTP/email verification instead.
This is why it fails with "Password page not loaded".

## Fix needed in panel_add_ui.py
After the name page, instead of waiting for password page,
we need to wait for the "Verify your email" OTP page and submit the code.

## Strategy - Use panel_add_ui.py
The panel_add_ui.py module already works. It navigates to the Kiro AI page,
finds the Add button, and does the device auth flow.
Let me use this to add more accounts. The key issue before was ERR-837 on the name page.
But we know new accounts use password → OTP → confirm flow, so it should work.

## What we know from the API
The panel stores Kiro connections with:
- provider: "kiro"
- authType: "oauth" 
- authMethod: "builder-id"
- startUrl: "https://view.awsapps.com/start"
- region: "us-east-1"
- profileArn: null
- clientId: base64 encoded string
- clientSecret: base64 encoded JSON with full OIDC registration

## Strategy
We need to:
1. Get a valid AWS SSO OIDC refresh token
2. POST it to /api/oauth/kiro/import with {"refreshToken": "<token>"}
3. The panel will use its OIDC client credentials to get an access token and add the account

## Getting the refresh token
The only reliable way is through the kiro-cli or direct OIDC API.
The kiro-cli approach fails because browser auth doesn't complete the device code flow.

## Alternative: Direct OIDC API with proper flow
We need to implement the full device flow correctly:
1. RegisterClient (client_name: "kiro-oauth-client", client_type: PUBLIC)
2. StartDeviceAuthorization (clientId, clientSecret, startUrl: https://view.awsapps.com/start)
3. Open verification URI in browser
4. Complete sign-in (email → password → OTP → confirm)
5. Call CreateToken (clientId, clientSecret, grant_type: urn:ietf:params:oauth:grant-type:device_code, device_code)

The issue before was that step 5 never succeeded. But let me try with the EXACT same client registration that the panel uses. The panel has a clientId for each connection - maybe we need to use the panel's client credentials.

Actually, the panel's clientSecret is per-connection. Each connection has its own clientId/clientSecret pair. The panel registers a new OIDC client for each Kiro connection.

So the flow should be:
1. Panel calls RegisterClient to get clientId/clientSecret
2. Panel calls StartDeviceAuthorization with those credentials
3. Panel opens the browser for user to auth
4. After auth, panel calls CreateToken to get refresh token
5. Panel stores the refresh token

But we're doing this manually. The panel's /api/oauth/kiro/import endpoint expects us to provide the refresh token. But to get the refresh token, we need to complete the OIDC flow ourselves.

## The Real Solution
Instead of trying to get the refresh token ourselves, let's use the panel's own device auth flow (which already works). The panel_add_ui.py script already does this successfully. The issue was only with the ERR-837 name page.

Since we now know accounts use password → OTP → confirm flow (not the name setup flow), the panel UI approach should work for new accounts too.

Let me go back to using panel_add_ui.py to add more accounts.
