# Critical Findings - Kiro Account Creation + Token Capture

## BREAKTHROUGH: OIDC Authorization Code Flow Works!
The correct flow is NOT the device code flow. It's the Authorization Code Flow with PKCE.

### Key Endpoints:
- Client registration: `POST https://oidc.us-east-1.amazonaws.com/client/register`
- Authorize URL: `https://oidc.us-east-1.amazonaws.com/authorize`
- Token endpoint: `https://oidc.us-east-1.amazonaws.com/token`

### Client Registration Payload:
```json
{
    "clientName": "kiro-xxx",
    "clientType": "public",
    "scopes": ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"],
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:PORT/oauth/callback"],
    "issuerUrl": "https://view.awsapps.com/start"
}
```

### Auth URL Format:
```
https://oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id=XXX&redirect_uri=http://127.0.0.1:PORT/oauth/callback&scopes=codewhisperer:completions codewhisperer:analysis codewhisperer:conversations codewhisperer:transformations codewhisperer:taskassist&state=XXX&code_challenge=XXX&code_challenge_method=S256
```

### Token Exchange Payload:
```json
{
    "clientId": "...",
    "clientSecret": "...",
    "grantType": "authorization_code",
    "code": "...",
    "codeVerifier": "...",
    "redirectUri": "http://127.0.0.1:PORT/oauth/callback"
}
```

## CRITICAL: SPA Render Timing
The AWS SSO portal SPA takes 50-75 seconds to fully render!
- `document.readyState` stays "loading" for ~50 seconds
- After "complete", body text appears
- Must wait for `readyState === 'complete'` AND `body.innerText.length > 50` before checking elements

## Signup Flow (discovered from debug):
1. Navigate to OIDC authorize URL → redirects to signup page at `signin.aws/platform/.../signup`
2. The signup page shows "Create your password" with email ALREADY PRE-FILLED (from the auth URL redirect)
3. Two password fields: "Enter password" and "Re-enter password"
4. Click "Continue"
5. OTP verification page appears
6. Extract OTP from Gmail (anshika31618@gmail.com via IMAP)
7. Fill OTP in text input, click "Verify"
8. Allow page appears
9. Click "Allow"
10. Browser redirects to localhost callback with auth code
11. Exchange auth code for tokens via `/token` endpoint

## OTP Extraction:
- Gmail: anshika31618@gmail.com
- App password: hlcv eobi tfwh terw
- IMAP server: imap.gmail.com
- Searches for emails FROM "no-reply@signin.aws" or "no-reply@login.awsapps.com" TO target email
- Extracts 6-digit code from email body

## Panel Status:
- Panel URL: https://ourproxy.sryze.cc/dashboard/providers
- Provider: kiro
- Password: 7894561230
- Status: DOWN (Cloudflare 530 error)
- Panel API: POST /api/oauth/kiro/import with body: {"refreshToken": "...", "region": "us-east-1", "authMethod": "builder-id", "startUrl": "https://view.awsapps.com/start", "name": "email"}

## Current Progress:
- 1 token successfully captured (account: hlh3sh6gb6@havenhaus.in)
- Script: /home/ubuntu/kiro-gen/final_production.py
- Output: /home/ubuntu/kiro-gen/captured_tokens.json and captured_tokens.csv

## What Still Needs To Be Done:
1. Run final_production.py for remaining accounts (need ~30 total)
2. Each account takes ~2-3 minutes (due to 50s SPA render time)
3. Once panel is back up, import tokens using the panel API
