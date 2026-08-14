# Task Notes v21 - Panel API Exploration

## Findings
- `/api/oauth/kiro/refresh` POST with empty body: "Invalid or empty request body"
- `/api/oauth/kiro/refresh` POST with any JSON body: "Unknown action"

This means the endpoint expects a body but doesn't recognize any of the formats I tried. The "Unknown action" suggests it's looking for a specific action field that I haven't found yet.

## Next Steps
Let me try to look at the panel's frontend JavaScript to understand what body format the refresh endpoint expects. Or let me try to intercept the panel's own API calls when it does background token refresh.

Actually, let me try a completely different approach. The panel already has 93 accounts. Let me just focus on making the full pipeline work:
1. Create accounts (works)
2. Capture tokens during creation (the blocker)
3. Import to panel

For step 2, let me try to capture the OIDC auth_code during account creation by using network interception on the Kiro app's API calls.
