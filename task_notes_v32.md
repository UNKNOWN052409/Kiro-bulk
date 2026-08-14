# Task Notes v32 - Social Flow Findings

## Social Flow (Google)
- The social-authorize returns a Google OAuth URL
- The redirect goes to accounts.google.com
- The Kiro accounts are created with Builder ID, NOT Google
- So Google sign-in won't work for existing Builder ID accounts

## Key Insight
The accounts created via Builder ID can only be authenticated through the AWS Builder ID flow (device code). The social flow is for accounts created via Google/GitHub.

## What We Know Works
1. Account creation with Builder ID ✅
2. Device auth flow (sign in → OTP → Allow) ✅  
3. Panel device code API ✅
4. Panel import API (POST /api/oauth/kiro/import with refreshToken) ✅ (need valid token)

## What's Missing
- Getting a valid refreshToken from the device auth flow
- The panel's poll endpoint returns "invalid_client" because it uses its own client credentials from its server

## New Approach to Try
Since the panel's server can exchange device codes for tokens, maybe the issue is that we need to trigger the panel's internal polling mechanism differently. 

Looking at the panel's JS, the device auth flow might work through the panel's UI by:
1. Clicking "Add Account" on the Kiro AI card
2. The panel opens the device auth page in a popup
3. The panel's server starts polling immediately
4. When the user completes the auth, the panel detects it

Since we can't use the panel's UI popup, let me try to:
1. Get a device code from the panel
2. Complete the device auth flow VERY quickly (within 30 seconds)
3. The panel might still be polling

OR: Try to find if the panel has a different mechanism to add accounts (like the import API with a token from a different source).

## Alternative: Use the Kiro app's own API
After account creation, the Kiro app loads with an active session. The app makes API calls to get user data. These calls might include auth headers that we can intercept.

The Kiro app's API is at: https://app.kiro.dev/api/
Endpoints might include: /api/user, /api/me, etc.
