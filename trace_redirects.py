"""
Trace the full OIDC redirect chain and capture the signin page HTML.
"""

import uuid, secrets, hashlib, base64, requests, json, re
from urllib.parse import quote, urlparse

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
print(f"Client ID: {client_id}")

# PKCE
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote("http://127.0.0.1:9997/oauth/callback")}'
            f'&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

print(f"\nAuth URL: {auth_url[:100]}...")

# Follow redirects manually, printing each step
session = requests.Session()
session.headers.update({'User-Agent': UA})

print("\n=== Following redirect chain ===")
urls = []
resp = session.get(auth_url, allow_redirects=False, timeout=30)
print(f"[0] {resp.status_code} {resp.url[:100]}")
urls.append(resp.url)

for i in range(10):
    loc = resp.headers.get('Location', '')
    if not loc:
        print(f"[{i}] No more redirects. Final page:")
        print(f"    URL: {resp.url[:120]}")
        print(f"    Status: {resp.status_code}")
        print(f"    Body length: {len(resp.text)}")
        # Save the HTML
        with open('/home/ubuntu/kiro-gen/signin_page.html', 'w') as f:
            f.write(resp.text)
        print(f"    Saved to signin_page.html")
        
        # Extract key elements
        # Look for workflowStateHandle
        ws = re.search(r'workflowStateHandle=([a-f0-9-]+)', resp.url)
        if ws:
            print(f"\n    workflowStateHandle: {ws.group(1)}")
        
        # Look for form elements
        inputs = re.findall(r'<input[^>]*>', resp.text)
        print(f"\n    Inputs found: {len(inputs)}")
        for inp in inputs[:10]:
            print(f"      {inp[:150]}")
        
        # Look for scripts
        scripts = re.findall(r'<script[^>]*src="([^"]+)"', resp.text)
        print(f"\n    Scripts: {scripts[:5]}")
        
        # Look for API endpoints in JS
        api_endpoints = re.findall(r'["\'](/api/[^"\']+)["\']', resp.text)
        print(f"\n    API endpoints: {api_endpoints[:10]}")
        
        # Look for fetch/axios calls
        fetches = re.findall(r'(?:fetch|axios)\(["\']([^"\']+)["\']', resp.text)
        print(f"\n    Fetch calls: {fetches[:5]}")
        
        # Look for form method/action
        forms = re.findall(r'<form[^>]*>', resp.text)
        print(f"\n    Forms: {forms[:3]}")
        
        break
    
    # Follow the redirect
    if loc.startswith('/'):
        # Relative URL
        from urllib.parse import urljoin
        loc = urljoin(resp.url, loc)
    print(f"[{i}] {resp.status_code} -> {loc[:100]}")
    urls.append(loc)
    
    try:
        resp = session.get(loc, allow_redirects=False, timeout=30)
    except Exception as e:
        print(f"    Error: {e}")
        break

print(f"\n=== URL chain ===")
for i, u in enumerate(urls):
    print(f"  [{i}] {u[:120]}")
