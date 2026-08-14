# Task Notes v31 - Social Authorize Response

The social-authorize endpoint returns:
```json
{
    "authUrl": "https://prod.us-east-1.auth.desktop.kiro.dev/login?idp=Google&redirect_uri=kiro%3A%2F%2Fkiro.kiroAgent%2Fauthenticate-success&code_challenge=...&code_challenge_method=S256&state=...&prompt=select_account",
    "state": "...",
    "codeVerifier": "...",
    "codeChallenge": "...",
    "provider": "google"
}
```

The redirect_uri is `kiro://kiro.kiroAgent/authenticate-success` - a custom scheme. When the browser tries to redirect to this, it will fail (no handler). But the auth server might include the `code` in the redirect URL before the browser fails.

Key insight: When the browser tries to navigate to `kiro://...`, Playwright will get an error but we can capture the URL that was attempted (which includes the auth code).

Alternative: The Kiro auth server might show the code on the page before redirecting, or we can intercept the redirect.
