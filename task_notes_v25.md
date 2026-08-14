# Task Notes v25 - Social Flow

## Key Findings
1. The panel's social-authorize only supports "google" and "github" providers
2. Builder ID and IDC are NOT supported through the social flow
3. The social flow uses PKCE with the Kiro auth server

## The Kiro Auth Server
- URL: `https://prod.us-east-1.auth.desktop.kiro.dev`
- Login endpoint: `/login?idp=<provider>&redirect_uri=<uri>&code_challenge=<challenge>&code_challenge_method=S256&state=<state>`
- Token endpoint: `/oauth/token` (returns 400 for device_code grant)
- Refresh endpoint: `/refreshToken`

## The Problem
- Builder ID accounts can't use the social flow (only Google/GitHub)
- The device code flow doesn't work externally (AWS returns 403)
- The Kiro auth token endpoint returns 400

## What We Know
- Account creation works (email → password → OTP via havenhaus.in → forwarded to Gmail Spam folder)
- Device auth flow works (email → password → OTP → Confirm → Allow → "Request approved")
- Panel import API: POST /api/oauth/kiro/import with {refreshToken: "..."}
- Panel validates the refresh token by trying to refresh it

## The Key Blocker
We can't get a valid refresh token to import to the panel.

## New Idea
The social flow uses Google/GitHub. But our accounts are Builder ID accounts. They can't use Google/GitHub sign-in.

However, looking at the Kiro auth server's login URL pattern:
`https://prod.us-east-1.auth.desktop.kiro.dev/login?idp=Google&...`

Maybe we can use `idp=builder-id` or `idp=idc` directly? Let me try.

Actually, looking at the authMethods in the panel's JS: ["builder-id", "idc", "google", "github", "import"]

The "import" auth method is interesting! Maybe there's a way to import accounts directly.

## Next Steps
1. Try the Kiro auth server login with idp=builder-id
2. Or try to capture the refresh token from the Kiro app after account creation
3. Or check if the panel's "import" auth method has a special API
