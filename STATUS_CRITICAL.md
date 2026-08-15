# CRITICAL FINDING

## The CONNECTION_ISSUE is NOT caused by the proxy!

Test WITHOUT proxy (direct VPS IP 37.215.41.189):
- Init: 200 ✓
- EmailForm: 200 ✓
- EmailSubmit: 200 ✓
- NameSubmit: 400 CONNECTION_ISSUE ✗

The name submit fails EVEN WITH A DIRECT CONNECTION. This means the issue is NOT the proxy creating different TLS connections.

## The real issue: AWS TES blocks the name submission step specifically

The pattern is:
1. All steps BEFORE email submit work (init, email form, email submit)
2. The step AFTER email submit (name submission) ALWAYS fails with CONNECTION_ISSUE

This suggests that AWS TES is doing something specific after the email submit:
- The email submit might trigger a security check
- The page might need to navigate to the signup page for the next step to work
- The workflow might be designed to only work from the actual signup page URL

## KEY INSIGHT
The email submit response has `redirect: {url: '/signup?workflowStateHandle=...'}`. This redirect is MANDATORY. The browser MUST navigate to the signup page before the name submission will work. The CONNECTION_ISSUE happens because the API call is being made from the wrong page context.

## SOLUTION
The browser MUST navigate to the signup page (the redirect URL from email submit). Then the name submission API call must be made from that page. The earlier "Failed to fetch" error when on the signup page might have been because we were using the wrong WS or the page wasn't fully loaded.

## NEXT STEPS
1. Navigate to the signup page after email submit
2. Wait for the page to fully load and stabilize
3. Make the name submission fetch from the signup page context
4. The fetch must use credentials: include and be same-origin (the signup page is on the same domain)
