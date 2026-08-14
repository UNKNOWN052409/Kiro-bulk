"""
Find the directory ID by examining the OIDC authorize redirect URL params.
"""

import uuid, secrets, hashlib, base64, requests, json
from urllib.parse import quote, urlparse, parse_qs

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

# Register OIDC client
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

code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote("http://127.0.0.1:9997/oauth/callback")}'
            f'&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

session = requests.Session()
session.headers.update({'User-Agent': UA})

# Get the first redirect
resp = session.get(auth_url, allow_redirects=False, timeout=30)
loc = resp.headers.get('Location', '')
print(f"Auth redirect: {loc}")

# Parse the start page URL params
parsed = urlparse(loc)
params = parse_qs(parsed.query)
print(f"\nStart page params:")
for k, v in params.items():
    print(f"  {k} = {v[0][:100] if len(v[0]) > 100 else v[0]}")

# Try calling login API with different directory IDs
print("\n=== Trying portal.sso login API ===")

# Try 1: directory_id = "view" (hostname split)
resp2 = session.get(
    'https://portal.sso.us-east-1.amazonaws.com/login',
    params={'directory_id': 'view', 'redirect_url': loc},
    timeout=30
)
print(f"  directory_id=view: {resp2.status_code}")
try:
    print(f"  Body: {resp2.text[:200]}")
except:
    pass

# Try 2: directory_id = "us-east-1" 
resp3 = session.get(
    'https://portal.sso.us-east-1.amazonaws.com/login',
    params={'directory_id': 'us-east-1', 'redirect_url': loc},
    timeout=30
)
print(f"  directory_id=us-east-1: {resp3.status_code}")
try:
    print(f"  Body: {resp3.text[:200]}")
except:
    pass

# Try 3: idcInstanceId = "d-9067642ac7" (the known directory from earlier)
resp4 = session.get(
    'https://portal.sso.us-east-1.amazonaws.com/login',
    params={'idcInstanceId': 'd-9067642ac7', 'redirect_url': loc},
    timeout=30
)
print(f"  idcInstanceId=d-9067642ac7: {resp4.status_code}")
try:
    data = resp4.json()
    print(f"  Response: {json.dumps(data, indent=2)[:300]}")
    redirect_url = data.get('redirectUrl', '')
    csrf_token = data.get('csrfToken', '')
    print(f"  redirectUrl: {redirect_url[:120]}")
    print(f"  csrfToken: {csrf_token[:50]}")
    
    if redirect_url:
        # Follow the redirect to signin.aws
        print("\n  Following redirect to signin.aws...")
        resp5 = session.get(redirect_url, allow_redirects=True, timeout=30)
        print(f"  Final URL: {resp5.url[:120]}")
        print(f"  Status: {resp5.status_code}")
        print(f"  Body: {resp5.text[:500]}")
        
        # Save HTML
        with open('/home/ubuntu/kiro-gen/signin_page.html', 'w') as f:
            f.write(resp5.text)
        print("  Saved to signin_page.html")
        
        # Extract form details
        import re
        inputs = re.findall(r'<input[^>]*>', resp5.text)
        print(f"\n  Inputs: {len(inputs)}")
        for inp in inputs[:20]:
            print(f"    {inp[:150]}")
        
        # Look for JavaScript bundles
        scripts = re.findall(r'<script[^>]*src="([^"]+)"', resp5.text)
        print(f"\n  Scripts: {scripts[:5]}")
        
        # Look for API endpoints
        api_eps = re.findall(r'["\'](/api/[^"\']+)["\']', resp5.text)
        print(f"\n  API endpoints: {api_eps[:10]}")
        
except Exception as e:
    print(f"  Error: {e}")
