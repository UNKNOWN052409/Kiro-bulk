# Task Notes v18 - Panel Token Exchange Issue

## Current Status
- Device auth flow works perfectly (email → password → OTP → Confirm → Allow → "Request approved")
- BUT the panel does NOT auto-detect the authorization
- The panel's server is supposed to poll the AWS token endpoint, but it doesn't
- AWS token endpoint returns 403 AccessDeniedException when called from outside (panel must call from its own server with proper credentials)

## Key Insight
The panel's device auth flow is designed to work ONLY through the panel's UI. The panel:
1. Gets device code
2. Opens the device auth page in the user's browser (through the panel's UI)
3. User completes authorization
4. Panel's server polls the AWS token endpoint (server-side, not client-side)

Since we're doing the browser part externally, the panel's server doesn't know to poll.

## Possible Solutions
1. **Use the panel's UI**: Click "Add Account" on the Kiro AI card through the panel's UI. The panel might open a popup/new tab with the device auth page and poll while it's open.
2. **Check panel logs**: The panel might have a "Console Log" section that shows what's happening.
3. **Check if there's a webhook/callback**: The panel might expect a callback from AWS.
4. **Use a different panel API**: There might be an API to manually add accounts with a refresh token.

## Panel Structure
- Custom Providers: vinay (22), kiro (Disabled), etc.
- OAuth Providers: Claude Code, Antigravity, etc.
- Free Tier Providers: **Kiro AI (93 Connected)** - this is where Kiro accounts are
- API Key Providers: Alibaba, Anthropic, etc.

## What We Know Works
1. Account creation (run_bot_patched.py)
2. Device auth flow (email → password → OTP → Confirm → Allow)
3. Panel login (POST /api/auth/login)
4. Panel device code API (GET /api/oauth/kiro/device-code)

## What Doesn't Work
- Panel auto-detecting external device auth completion
- Direct AWS token endpoint polling (403 AccessDenied)
- Panel import API (/api/oauth/kiro/import returns 404)

## Next Steps to Try
1. Check the panel's "Console Log" section for any device auth related logs
2. Try clicking "Add Account" through the panel's UI (if such a button exists)
3. Check if the panel has a "Test All" button that might trigger polling
4. Look at the panel's network requests to understand the device auth flow
