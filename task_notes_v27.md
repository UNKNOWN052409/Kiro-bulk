# Task Notes v27 - POLL ENDPOINT DISCOVERED!

## BREAKTHROUGH
The panel has a `/api/oauth/kiro/poll` endpoint that accepts `{"deviceCode": "..."}` and returns:
```json
{"success":false,"error":"invalid_client","errorDescription":"Invalid client provided","pending":false}
```

This means the panel's server calls the AWS token endpoint with the device code + client credentials to get tokens!

## The "invalid_client" Error
This error means the panel's client credentials are being rejected by AWS. This might be because:
1. The device code hasn't been authorized yet (need to complete sign-in first)
2. The client credentials are wrong/expired
3. The AWS token endpoint URL is different from what the panel uses

## Full Flow
1. Get device code: GET /api/oauth/kiro/device-code?start_url=...&region=us-east-1&auth_method=idc
2. Complete device auth (browser): email → password → OTP → Confirm → Allow
3. Poll: POST /api/oauth/kiro/poll with {"deviceCode": "..."}
4. If success, the account is added to the panel!

## Script Location
/tmp/test_poll_import.py - complete script that does the full flow

## Account Credentials
- Email: nicholas204@havenhaus.in
- Password: pI6z7GxxO1iMoQ27#=

## OTP
- OTP emails go to Gmail Spam folder ([Gmail]/Spam)
- Extract 6-digit code from body
- fetch_emails from mail_reader module
