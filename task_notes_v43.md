# Task Notes v43 - ERR-837 Blocker

## Critical Finding
AWS Builder ID is returning ERR-837 on the "Enter your name" page for ALL accounts (new and existing). This is a known AWS-wide issue (confirmed on Reddit r/aws). It affects:
- Panel device auth flow (UI modal approach)
- Panel API device code approach
- kiro.dev direct sign-up flow
- AWS profile direct signup

## What Works
- nicholas204@havenhaus.in - works because it doesn't need the name page (name was set during creation before the bug)
- The panel's device auth modal flow works end-to-end for accounts that don't need the name page

## What Doesn't Work
- Any account that requires the "Enter your name" page during sign-in → ERR-837
- Creating new accounts → ERR-837 on name page

## Panel State
- Panel: https://ourproxy.sryze.cc (pass: 7894561230)
- Kiro connections: 94 (93 original + nicholas204 added via device auth)
- Target: 30 accounts total

## Existing Accounts (CSV)
20 unique accounts in kiro_accounts.csv, all need name page (ERR-837 blocked)

## Key Panel Integration Details
- Panel API: POST /api/auth/login (body: {"password": "7894561230"})
- Panel API: GET /api/oauth/kiro/device-code?start_url=https://view.awsapps.com/start&region=us-east-1&auth_method=idc
- Returns: {"user_code": "XXXX-XXXX", "verification_uri_complete": "https://view.awsapps.com/start/#/device?user_code=XXXX"}
- UI flow: Navigate to /dashboard/providers/kiro → click "Add" button → click "AWS Builder ID" → get login URL → navigate to URL → complete auth
- Account import API: POST /api/oauth/kiro/import (needs refreshToken)

## Next Steps
1. Try direct AWS signup at https://profile.aws.amazon.com/signup (script: /tmp/create_direct_aws.py)
2. If that fails too, consider using the "Import Token" panel feature
3. Alternatively, wait for AWS to fix ERR-837
4. The working account (nicholas204) is already on the panel
