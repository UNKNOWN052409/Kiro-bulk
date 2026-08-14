# Critical Finding: AWS SSO Portal SPA Render Timing

## Issue
The AWS SSO portal SPA (view.awsapps.com/start) takes 50+ seconds to fully render. The `document.readyState` stays "loading" for ~50 seconds before switching to "complete". Before that, `document.body.innerText` is empty and no inputs/buttons are visible.

## Evidence
- At 0-45s: readyState="loading", bodyText=0, mainContainer=0
- At 50s: readyState="complete", mainContainer=1312
- At 55s: bodyText=115 (shows "Privacy | Site terms | Cookie preferences")
- At 75s: Full body text shows login form ("Get started", "Email", "Continue", etc.)

## Root Cause
The SPA's JavaScript bundle (app.js + chunks) is large and takes a long time to download and execute in the sandbox environment. The page returns a minimal HTML shell immediately, then loads JS asynchronously.

## Solution
Always wait for `document.readyState === 'complete'` AND `document.body.innerText.length > 50` before checking for elements. This requires waiting 50-75 seconds after each navigation.

## Key Selectors (after full render)
- Email input: `input[type="email"]` (placeholder: username@example.com)
- Continue button: `button` with text "Continue"
- Cookie buttons: "Accept", "Decline", "Customize", "Cancel", "Save preferences", "Dismiss"
- Sign out: `text=Sign out`
- Allow button: `button` with text "Allow" or "Allow access"

## Login Page Structure (after render)
```
Get started
Email [input type=email placeholder=username@example.com]
Continue [button]
OR
Continue with Google [button]
Continue with Apple [button]
Continue with GitHub [button]
Continue with Amazon [button]
```

## Batch Script Timing
Each account takes approximately:
- Navigation + render: 60-75 seconds
- Email fill + submit: 10 seconds
- Render again: 60 seconds
- Name fill + submit: 10 seconds
- OTP: 10 seconds (if needed)
- Password + submit: 10 seconds
- Allow click: 5 seconds
- Logout: 70 seconds
- Total per account: ~200-250 seconds (3-4 minutes)

For 10 accounts: ~30-40 minutes total.
