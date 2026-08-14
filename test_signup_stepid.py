"""Test different stepId values for signup"""
import uuid, requests, json, time, random, re
from urllib.parse import quote
import secrets, hashlib, base64

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

code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
state = secrets.token_urlsafe(16)
redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
scopes_encoded = ' '.join(GRANT_SCOPES)
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

session = requests.Session()
session.proxies = {'http': PROXY_URL, 'https': PROXY_URL}
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
})

# Follow redirects to get WSH
resp1 = session.get(auth_url, allow_redirects=True, timeout=60)
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
resp2 = session.get(portal_url, allow_redirects=True, timeout=30)
match = re.search(r'workflowStateHandle["\']?\s*[:=]\s*["\']?([0-9a-f-]{36})', resp2.text)
wsh = match.group(1)
print(f"WSH: {wsh}")

headers = {
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': f'https://{REGION}.signin.aws',
    'Referer': f'https://{REGION}.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={wsh}',
}

# Email submit
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
data = resp.json()
wsh2 = data.get('workflowStateHandle', '')
print(f"Email: HTTP {resp.status_code}, New WSH: {wsh2}")
print(f"  stepId in response: {data.get('stepId', 'N/A')}")
print(f"  workflow-step-id cookie: {session.cookies.get('workflow-step-id', 'N/A')}")

time.sleep(1)

# Try signup with different stepId values
test_cases = [
    ("get-identity-user", "SIGNUP"),
    ("start", "SIGNUP"),
    ("get-identity-user", ""),
    ("", "SIGNUP"),
]

for step_id, action_id in test_cases:
    signup_payload = {
        "stepId": step_id,
        "workflowStateHandle": wsh2,
        "actionId": action_id,
        "inputs": [
            {"input_type": "UserRequestInput", "username": email},
            {"input_type": "FingerPrintRequestInput", "fingerPrint": FP}
        ],
        "visitorId": str(uuid.uuid4()),
        "requestId": str(uuid.uuid4())
    }
    resp = session.post(f'https://{REGION}.signin.aws/platform/d-9067642ac7/api/execute', 
                       json=signup_payload, headers=headers, timeout=30)
    print(f"\n  stepId='{step_id}', actionId='{action_id}': HTTP {resp.status_code}")
    if resp.status_code == 200:
        d = resp.json()
        print(f"    New WSH: {d.get('workflowStateHandle', 'N/A')}")
        print(f"    stepId: {d.get('stepId', 'N/A')}")
        break
    else:
        print(f"    Error: {resp.text[:150]}")

# Also try without actionId
print("\n  No actionId (just stepId='start'):")
signup_payload = {
    "stepId": "start",
    "workflowStateHandle": wsh2,
    "inputs": [
        {"input_type": "UserRequestInput", "username": email},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": FP}
    ],
    "visitorId": str(uuid.uuid4()),
    "requestId": str(uuid.uuid4())
}
resp = session.post(f'https://{REGION}.signin.aws/platform/d-9067642ac7/api/execute', 
                   json=signup_payload, headers=headers, timeout=30)
print(f"    HTTP {resp.status_code}")
if resp.status_code == 200:
    d = resp.json()
    print(f"    New WSH: {d.get('workflowStateHandle', 'N/A')}")
    print(f"    stepId: {d.get('stepId', 'N/A')}")
else:
    print(f"    Error: {resp.text[:150]}")
