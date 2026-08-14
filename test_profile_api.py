#!/usr/bin/env python3
"""
Test: After signup API, try to get workflowID from profile.aws.amazon.com
The profile SPA might accept workflowStateHandle and generate workflowID
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
from urllib.parse import quote, urlparse

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'

with open('/home/ubuntu/kiro-gen/cloak_fingerprint.txt', 'r') as f:
    CLOAK_FP = f.read().strip()
with open('/home/ubuntu/kiro-gen/profile_fingerprint.txt', 'r') as f:
    PROFILE_FP = f.read().strip()

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

# Register
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9997/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

# PKCE
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = 'http://127.0.0.1:9997/oauth/callback'
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

# Create session with proxy
session = requests.Session()
proxy_url = f"socks5://api-US:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
session.proxies = {'http': proxy_url, 'https': proxy_url}
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
})

# Get WSH
email_addr = generate_email()
current_url = auth_url
wsh = None
for i in range(15):
    try:
        resp = session.get(current_url, allow_redirects=False, timeout=15)
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get('Location', '')
            if location:
                if location.startswith('/'):
                    parsed = urlparse(current_url)
                    current_url = f"{parsed.scheme}://{parsed.netloc}{location}"
                else:
                    current_url = location
                if 'workflowStateHandle=' in current_url:
                    wsh = current_url.split('workflowStateHandle=')[1].split('&')[0]
                    break
        elif resp.status_code == 200:
            if 'workflowStateHandle=' in current_url:
                wsh = current_url.split('workflowStateHandle=')[1].split('&')[0]
                break
            if 'awsapps.com/start' in current_url and 'orchestrator_id=' in current_url:
                parts = current_url.split('?')[1]
                orch_id = None
                cb_url = None
                for part in parts.split('&'):
                    if part.startswith('orchestrator_id='):
                        orch_id = part.split('=', 1)[1]
                    elif part.startswith('callback_url='):
                        cb_url = part.split('=', 1)[1]
                if orch_id:
                    portal_url = f"https://portal.sso.us-east-1.amazonaws.com/login?directory_id=view&orchestrator_id={orch_id}"
                    if cb_url:
                        portal_url += f"&callback_url={cb_url}"
                    current_url = portal_url
                    continue
            if 'portal.sso' in current_url:
                match = re.search(r'window\.location[^=]*=\s*["\']([^"\']+)', resp.text)
                if match:
                    loc = match.group(1)
                    if loc.startswith('/'):
                        current_url = f"https://portal.sso.us-east-1.amazonaws.com{loc}"
                    else:
                        current_url = loc
                    continue
            break
    except Exception as e:
        print(f"  Error at step {i}: {e}")
        break

print(f"WSH: {wsh}")
print(f"Email: {email_addr}")

headers = {
    'Content-Type': 'application/json;charset=UTF-8',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://us-east-1.signin.aws',
    'Referer': f'https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={wsh}',
}

visitor_id = str(uuid.uuid4())

# Submit email
email_payload = {
    "stepId": "get-identity-user",
    "workflowStateHandle": wsh,
    "actionId": "SUBMIT",
    "inputs": [
        {"input_type": "UserRequestInput", "username": email_addr},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FP}
    ],
    "visitorId": visitor_id,
    "requestId": str(uuid.uuid4())
}

email_resp = session.post(
    f'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute',
    json=email_payload, headers=headers, timeout=30
)
print(f"Email: HTTP {email_resp.status_code}")

# Signup call 1: stepId=""
signup1_payload = {
    "stepId": "",
    "workflowStateHandle": wsh,
    "inputs": [
        {"input_type": "UserRequestInput", "username": email_addr},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FP}
    ],
    "visitorId": visitor_id,
    "requestId": str(uuid.uuid4())
}

signup1_resp = session.post(
    f'https://us-east-1.signin.aws/platform/d-9067642ac7/signup/api/execute',
    json=signup1_payload, headers=headers, timeout=30
)
print(f"Signup1: HTTP {signup1_resp.status_code}")
data1 = signup1_resp.json()
wsh2 = data1.get('workflowStateHandle', '')
print(f"  New WSH from signup: {wsh2}")

# Now try to get workflowID from profile.aws.amazon.com
print(f"\n--- Trying profile.aws.amazon.com APIs ---")

# Try 1: GET profile.aws.amazon.com with WSH (might redirect with workflowID)
print("\n[1] GET profile.aws.amazon.com/?workflowStateHandle=WSH")
try:
    profile_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    profile_resp = session.get(
        f'https://profile.aws.amazon.com/?workflowStateHandle={wsh2}',
        headers=profile_headers,
        allow_redirects=False,
        timeout=30
    )
    print(f"  Status: {profile_resp.status_code}")
    if profile_resp.status_code in (301, 302, 303, 307, 308):
        loc = profile_resp.headers.get('Location', '')
        print(f"  Redirect: {loc[:200]}")
        if 'workflowID=' in loc:
            workflow_id = loc.split('workflowID=')[1].split('&')[0]
            print(f"  FOUND workflowID: {workflow_id}")
    else:
        print(f"  Body length: {len(profile_resp.text)}")
        # Check for workflowID in body
        if 'workflowID' in profile_resp.text:
            match = re.search(r'workflowID["\']?\s*[:=]\s*["\']?([0-9a-f-]{36})', profile_resp.text)
            if match:
                print(f"  FOUND workflowID in body: {match.group(1)}")
except Exception as e:
    print(f"  Error: {e}")

# Try 2: POST to profile API with WSH
print("\n[2] POST /api/start with workflowStateHandle instead of workflowID")
try:
    profile_api_headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://profile.aws.amazon.com',
    }
    
    # Try with workflowStateHandle
    start_payload = {
        "workflowStateHandle": wsh2,
        "browserData": {
            "attributes": {"fingerprint": PROFILE_FP},
            "cookies": []
        }
    }
    
    start_resp = session.post(
        'https://profile.aws.amazon.com/api/start',
        json=start_payload,
        headers=profile_api_headers,
        timeout=30
    )
    print(f"  Status: {start_resp.status_code}")
    print(f"  Response: {start_resp.text[:500]}")
    
    if start_resp.status_code == 200:
        data = start_resp.json()
        print(f"  Keys: {list(data.keys())}")
        if 'workflowID' in data:
            print(f"  FOUND workflowID: {data['workflowID']}")
except Exception as e:
    print(f"  Error: {e}")

# Try 3: GET app-context with WSH
print("\n[3] POST /api/get-app-context with workflowStateHandle")
try:
    ctx_payload = {"workflowStateHandle": wsh2}
    ctx_resp = session.post(
        'https://profile.aws.amazon.com/api/get-app-context',
        json=ctx_payload,
        headers=profile_api_headers,
        timeout=30
    )
    print(f"  Status: {ctx_resp.status_code}")
    print(f"  Response: {ctx_resp.text[:300]}")
except Exception as e:
    print(f"  Error: {e}")

# Try 4: Use the signup WSH as workflowID directly
print("\n[4] POST /api/start with workflowStateHandle as workflowID")
try:
    start_payload2 = {
        "workflowID": wsh2,
        "browserData": {
            "attributes": {"fingerprint": PROFILE_FP},
            "cookies": []
        }
    }
    
    start_resp2 = session.post(
        'https://profile.aws.amazon.com/api/start',
        json=start_payload2,
        headers=profile_api_headers,
        timeout=30
    )
    print(f"  Status: {start_resp2.status_code}")
    print(f"  Response: {start_resp2.text[:500]}")
except Exception as e:
    print(f"  Error: {e}")

print(f"\n{'='*60}")
