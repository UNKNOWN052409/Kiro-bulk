"""Test to understand the cookie flow for /signup/api/execute"""
import uuid, requests, json, time, random, re
from urllib.parse import quote

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_URL = f'socks5://res-US:{PROXYRISE_API_KEY}@gw.proxyrise.com:443'
CALLBACK_PORT = 9997
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis"]
ISSUER_URL = 'https://view.awsapps.com/start'

FP = "ECdITeCs:UWRUrFnpdafZC4o3qLX0QO1zM7GGRhBYbCdxhFE3KyPZG9Lf4lIloheptWDhxz/1LQaPyITBH3ENdUL7ioopHDd2xwY6GW3YypMAEK/DWYWjZkn0D/oAW9r6lQZ5MO8IYkiAE8gLNieF3DJAisXZ8BJ9e9YkXsm7775J7212u+049rn6UJOg2ybbEcUsq/mfR4P79AJaskeY7YKjkDHIdBN4ALIXTrpedUK3NHpiKidzeFHAzf8FxtWLGk7DsTKor42RrzR+luULhPFIlZlL"

email = f"test{uuid.uuid4().hex[:8]}@havenhaus.in"

# Register OIDC client (no proxy)
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code"],
    "redirectUris": [f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']
print(f"Client ID: {client_id}")

import secrets, hashlib, base64
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
state = secrets.token_urlsafe(16)
redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
scopes_encoded = ' '.join(GRANT_SCOPES)
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

# Session with proxy
session = requests.Session()
session.proxies = {'http': PROXY_URL, 'https': PROXY_URL}
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
})
from requests.adapters import HTTPAdapter
session.mount('http://', HTTPAdapter(max_retries=3))
session.mount('https://', HTTPAdapter(max_retries=3))

# Follow redirects
print("\n[1] OIDC authorize -> redirects...")
resp1 = session.get(auth_url, allow_redirects=True, timeout=60)
print(f"    Final URL: {resp1.url[:120]}...")
print(f"    Cookies after redirect: {dict(session.cookies)}")

# If on view.awsapps.com, navigate to portal.sso
if 'view.awsapps.com' in resp1.url:
    orch_id = ''
    cb_url = ''
    for part in resp1.url.split('?')[1].split('&'):
        if part.startswith('orchestrator_id='):
            orch_id = part.split('=',1)[1]
        elif part.startswith('callback_url='):
            cb_url = part.split('=',1)[1]
    portal_url = f"https://portal.sso.{REGION}.amazonaws.com/login?directory_id=view&orchestrator_id={orch_id}"
    if cb_url:
        portal_url += f"&callback_url={cb_url}"
    print(f"\n[2] Portal.sso...")
    resp2 = session.get(portal_url, allow_redirects=True, timeout=30)
    print(f"    Portal URL: {resp2.url[:80]}...")
    print(f"    Cookies: {dict(session.cookies)}")
    
    match = re.search(r'workflowStateHandle["\']?\s*[:=]\s*["\']?([0-9a-f-]{36})', resp2.text)
    if not match:
        print("    No WSH found in portal HTML!")
        print(f"    HTML length: {len(resp2.text)}")
        exit(1)
    wsh = match.group(1)
    print(f"    WSH: {wsh}")
    
    # Also check for signin.aws redirect in HTML
    signin_match = re.search(r'(https://[^"\']*(?:signin|login)[^"\']*workflowStateHandle[^"\']*)', resp2.text)
    if signin_match:
        print(f"    Signin URL in HTML: {signin_match.group(1)[:100]}...")
else:
    print(f"Unexpected URL: {resp1.url}")
    exit(1)

# Email submit
print(f"\n[3] Email submit...")
headers = {
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': f'https://{REGION}.signin.aws',
    'Referer': f'https://{REGION}.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={wsh}',
}
payload = {
    "stepId": "get-identity-user",
    "workflowStateHandle": wsh,
    "actionId": "SUBMIT",
    "inputs": [
        {"input_type": "UserRequestInput", "username": email},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": FP}
    ],
    "visitorId": str(uuid.uuid4()),
    "requestId": str(uuid.uuid4())
}
resp = session.post(f'https://{REGION}.signin.aws/platform/d-9067642ac7/api/execute', json=payload, headers=headers, timeout=30)
print(f"    HTTP {resp.status_code}")
data = resp.json()
wsh2 = data.get('workflowStateHandle', '')
print(f"    New WSH: {wsh2}")
print(f"    Cookies: {dict(session.cookies)}")

time.sleep(1)

# Signup
print(f"\n[4] Signup (actionId=SIGNUP)...")
payload3 = dict(payload)
payload3['actionId'] = 'SIGNUP'
payload3['workflowStateHandle'] = wsh2
payload3['requestId'] = str(uuid.uuid4())
resp3 = session.post(f'https://{REGION}.signin.aws/platform/d-9067642ac7/api/execute', json=payload3, headers=headers, timeout=30)
print(f"    HTTP {resp3.status_code}")
data3 = resp3.json()
wsh3 = data3.get('workflowStateHandle', '')
print(f"    New WSH: {wsh3}")
print(f"    Cookies: {dict(session.cookies)}")
print(f"    Set-Cookie: {resp3.headers.get('Set-Cookie', 'none')}")

time.sleep(1)

# Navigate to /signup page
print(f"\n[5] GET /signup page...")
signup_url = f'https://{REGION}.signin.aws/platform/d-9067642ac7/signup?workflowStateHandle={wsh3}'
page_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': f'https://{REGION}.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={wsh2}',
}
resp4 = session.get(signup_url, headers=page_headers, timeout=30)
print(f"    HTTP {resp4.status_code}, len={len(resp4.text)}")
print(f"    Cookies after GET: {dict(session.cookies)}")
print(f"    Set-Cookie: {resp4.headers.get('Set-Cookie', 'none')}")
print(f"    HTML snippet: {resp4.text[:200]}")

time.sleep(1)

# Check cookies on all cookies jar
print(f"\n    ALL cookies: {session.cookies.get_dict()}")

# POST to /signup/api/execute
print(f"\n[6] POST /signup/api/execute (stepId='')...")
signup_headers = {
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': f'https://{REGION}.signin.aws',
    'Referer': signup_url,
}
payload5 = {
    "stepId": "",
    "workflowStateHandle": wsh3,
    "inputs": [
        {"input_type": "UserRequestInput", "username": email},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": FP}
    ],
    "visitorId": str(uuid.uuid4()),
    "requestId": str(uuid.uuid4())
}
resp5 = session.post(f'https://{REGION}.signin.aws/platform/d-9067642ac7/signup/api/execute', json=payload5, headers=signup_headers, timeout=30)
print(f"    HTTP {resp5.status_code}")
print(f"    Response: {resp5.text[:300]}")
