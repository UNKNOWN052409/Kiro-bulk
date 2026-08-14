# Task Notes v16 - Token Endpoint

## AWS OIDC Token Endpoint
- URL: https://oidc.us-east-1.amazonaws.com/oauth2/token
- Returns 403 AccessDeniedException when called directly
- The panel must be calling this endpoint from its server (not from client)

## Key Finding
The panel's device auth flow works like this:
1. Panel gets device code from AWS (stores clientId, clientSecret, deviceCode)
2. User completes authorization on AWS device page
3. Panel's SERVER polls the AWS token endpoint with the device code
4. Panel receives access_token + refresh_token
5. Panel creates a connection with the refresh_token

The issue is: the panel doesn't know we completed the authorization because we did it through our script, not through the panel's UI. The panel might be polling periodically, or it might need a trigger.

## Solution
The panel might need us to:
1. Complete the device auth flow (done ✅)
2. The panel should automatically detect and add the account
3. OR we need to trigger the panel's polling mechanism

Since the panel returned 4 active accounts earlier (Account 90-93), it seems like it CAN add accounts. The issue might be that the panel only polls for a limited time after getting the device code.

## Next Steps
1. Get a fresh device code from panel
2. Complete the full device auth flow
3. Immediately check if the panel adds the account (within 60 seconds)
4. If not, the panel might need to be triggered differently

## Working Credentials
- nicholas204@havenhaus.in / wbh$b999%%EbC-
- OTP: extracted from Gmail SPAM folder (subject: "Verify your identity")

## Script
/tmp/test_device_auth_v2.py - the complete working script
