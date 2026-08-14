# API-Only Account Creation (No Browser) - Status

## Key Finding
- profile.aws.amazon.com NEVER renders through ANY proxy (SPA blocked at domain level)
- Without proxy: loads fine but ERR-837 on submission
- Solution: Use MITM-captured API calls directly, NO BROWSER needed

## MITM-Captured API Flow
1. Register OIDC client: POST https://oidc.us-east-1.amazonaws.com/client/register
2. GET authorize URL → redirect chain → login page with workflowStateHandle
3. POST /api/execute (fingerprint)
4. POST /api/execute (email, actionId=SUBMIT)
5. POST /api/execute (actionId=SIGNUP)
6. GET profile.aws.amazon.com/?workflowID=UUID
7. POST /api/get-config
8. POST /api/get-app-context
9. POST /api/start (returns workflowState)
10. POST /api/send-otp
11. Enter OTP → submit password → capture tokens

## Fingerprints
- /home/ubuntu/kiro-gen/cloak_fingerprint.txt (6065 chars) - signin.aws
- /home/ubuntu/kiro-gen/profile_fingerprint.txt (5989 chars) - profile.aws

## ProxyRise
- API Key: pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1
- SOCKS5: socks5://api-US:API_KEY@gw.proxyrise.com:443
- Works with requests library via SOCKS5

## Headers for API calls
```python
{
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Content-Type': 'application/json;charset=UTF-8',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://us-east-1.signin.aws',
    'Referer': 'https://us-east-1.signin.aws/platform/d-9067642ac7/login',
}
```

## The Missing Piece - Getting workflowStateHandle without browser
The redirect chain from authorize URL:
1. oidc.us-east-1.amazonaws.com/authorize → 302
2. view.awsapps.com/start/?callback_url=...&orchestrator_id=... → 302 (JS redirect)
3. portal.sso.us-east-1.amazonaws.com/login → 302
4. us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle=UUID

Step 2 uses JavaScript redirect, not HTTP redirect.
BUT we can manually make the request that the JS would make:
GET https://portal.sso.us-east-1.amazonaws.com/login?directory_id=view&redirect_url=<encoded>
This should return redirect to signin.aws with workflowStateHandle.
