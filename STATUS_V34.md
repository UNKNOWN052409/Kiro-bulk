# Kiro Account Creator - Status V34

## Current State
Steps 1-4 work perfectly (OIDC register, browser navigate, init, email form load, email submit with SIGNUP action).
Step 5 (name submission on signup API) consistently fails with HTTP 400 "Please try signing in again".

## Key Findings
1. Login API: `https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute` - WORKS
2. Signup API: `https://us-east-1.signin.aws/platform/d-9067642ac7/signup/api/execute` - init/name form load WORKS (200), but name SUBMIT returns 400
3. `profile.aws.amazon.com/api/execute` - does NOT work (returns 400 INVALID_WORKFLOW_STATE_HANDLE)
4. The WS from email submit redirect is NOT valid on the signup API
5. The signup API init with fresh WS works (returns step='start'), but name submit on the returned step fails

## The Core Problem
The name submit on the signup API always returns 400 with empty actionIdList. The step `get-verified-username` doesn't accept any actions.

## Proxy Status
- SOCKS5 wrapper works: `proxy_socks5_wrapper.py` on port 8899
- It bridges local HTTP CONNECT to ProxyRise SOCKS5 gateway
- ProxyRise: `socks5://res-us:{API_KEY}@gw.proxyrise.com:443`
- API Key: `pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1`
- Browser uses `proxy={'server': 'http://127.0.0.1:8899'}`
- Direct SOCKS5 from Playwright fails with ERR_SOCKS_CONNECTION_FAILED

## What Still Needs To Be Figured Out
The correct step/action for name submission on the signup API. Possibilities:
1. The signup flow might need a different input key (not 'verifiedUserName')
2. The actionId might need to be something other than 'SUBMIT' or 'SIGNUP'
3. The signup API might need cookies from the browser session on that domain
4. The email submit response might contain a different redirect that we're not parsing correctly

## Email Submit Response Structure (from main script)
```json
{
  "status": 200,
  "stepId": "user-signup",
  "workflowStateHandle": "64ba614f-7948-4d63-9c7...",
  "redirect": {"url": "https://us-east-1.signin.aws/platform/d-9067642ac7/signup?workflowStateHandle=..."}
}
```

## Files
- `/home/ubuntu/kiro-gen/kiro_final.py` - main script (steps 1-4 work, step 5 fails)
- `/home/ubuntu/kiro-gen/proxy_socks5_wrapper.py` - working SOCKS5-to-HTTP proxy wrapper
- `/home/ubuntu/kiro-gen/api_only_creator.py` - reference using profile.aws.amazon.com (doesn't work)
- `/home/ubuntu/kiro-gen/capture_signup.py` - debug script (fails without OIDC flow)
- `/home/ubuntu/kiro-gen/debug_signup2.py` - debug script (page stuck on awsapps.com)
