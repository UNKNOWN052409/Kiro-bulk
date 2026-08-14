# Task Notes v22 - Import API Found!

## BREAKTHROUGH
The panel's `/api/oauth/kiro/import` endpoint:
- Method: POST
- Body: `{"refreshToken": "<refresh_token>"}`
- Works! Returns error for fake tokens: `{"error":"Token refresh failed: {\"message\":\"Bad credentials\"}"}`
- This means the panel validates the refresh token by trying to use it (calling AWS token endpoint)

## What We Need
A valid AWS OIDC refresh token for a Kiro account. The refresh token is obtained from the AWS OIDC token endpoint after completing the authorization code flow.

## How to Get Refresh Token
The refresh token comes from the AWS OIDC token exchange:
```
POST https://oidc.us-east-1.amazonaws.com/oauth2/token
grant_type=authorization_code
code=<auth_code>
client_id=<client_id>
client_secret=<client_secret>
redirect_uri=http://localhost:3128/signin/callback
```

OR from the device code flow:
```
POST https://oidc.us-east-1.amazonaws.com/oauth2/token
grant_type=urn:ietf:params:oauth:grant-type:device_code
device_code=<device_code>
client_id=<panel_client_id>
client_secret=<panel_client_secret>
```

## The Problem
1. During account creation, the Kiro SPA intercepts the redirect and we can't capture the auth_code
2. The device code flow works (we can complete it) but the AWS token endpoint returns 403 when called from outside (panel must call it from its own server)

## Solution
We need to complete the device auth flow AND then call the AWS token endpoint with the panel's client credentials. But the panel's server does this internally.

Alternative: The panel has `/api/oauth/kiro/auto-import` which auto-detects tokens. But this is for local tokens.

Another approach: The panel's `/api/oauth/kiro/import` endpoint validates the refresh token. If we can get a valid refresh token from ANY source, we can import it.

The refresh token format is typically a long JWT-like string from AWS OIDC.

## Key Insight
The panel's device auth flow (Strategy 2 in the bot) probably:
1. Gets device code with panel's client credentials
2. User completes authorization
3. Panel's server calls AWS token endpoint with device_code + client_id + client_secret
4. Gets refresh token
5. Stores it in the database

Since we can't make the panel's server poll, we need to either:
A. Find a way to trigger the panel to poll
B. Get the refresh token ourselves and use the import API

For option B, we need to find a client_id/client_secret that we can use to call the AWS token endpoint. The panel's client credentials are returned in the device code response!
