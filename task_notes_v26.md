# Task Notes v26 - Panel Device Auth Flow (from JS analysis)

## How the Panel Does Device Auth (from JS)
```javascript
// For "kiro" provider:
let e = new URL(`/api/oauth/${t}/device-code`, window.location.origin);
// kiro === t, so it adds params:
e.searchParams.set("start_url", u.startUrl);  // https://view.awsapps.com/start
e.searchParams.set("region", u.region);        // us-east-1
e.searchParams.set("auth_method", "idc");

// Get device code
let a = await fetch(e.toString());
let s = await a.json();

// Open the verification URI in a new tab
let r = s.verification_uri_complete || s.verification_uri;
window.open(r, "_blank", "noopener,noreferrer");

// Store client info
let n = {_clientId: s._clientId, _clientSecret: s._clientSecret, _region: s._region, _authMethod: s._authMethod, _startUrl: s._startUrl};
```

The panel:
1. Gets device code from `/api/oauth/kiro/device-code`
2. Opens the AWS device auth page in a new tab
3. The user signs in on that page
4. The panel's SERVER polls the AWS token endpoint with the device code + client credentials
5. When the token is obtained, the panel creates a connection

## The Key Issue
The panel's SERVER polls the AWS token endpoint. Since we're doing the browser part externally, the panel's server doesn't know to poll (or it stops polling after a timeout).

## Solution Ideas
1. **Trigger the panel's polling**: Maybe there's an API to tell the panel to start polling for a specific device code
2. **Do the token exchange ourselves**: The panel returns the client credentials in the device code response. We should be able to call the AWS token endpoint with these. But we get 403.
3. **Wait for the panel to detect**: Maybe the panel polls periodically and will eventually detect our authorization

## Let me try #3 - complete the device auth flow and then wait for the panel to detect it
The panel might have a background job that polls for pending device codes.

## Also, let me look at the panel's backend API for any "poll" or "check" endpoint
The panel's console log showed:
```
[TOKEN_REFRESH] Credentials updated in localDb
[BG_TOKEN_REFRESH] Connection refresh finished
```

This suggests the panel has a background task that refreshes tokens. Maybe it also checks for pending device auth requests.
