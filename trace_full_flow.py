"""
Trace the complete flow step by step:
1. OIDC authorize -> view.awsapps.com/start
2. Call portal.sso.us-east-1.amazonaws.com/login API
3. Follow redirect to signin.aws
4. Capture the signin page HTML and form structure
"""

import uuid, secrets, hashlib, base64, requests, json, re
from urllib.parse import quote, urlparse, urljoin

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

session = requests.Session()
session.headers.update({
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})

# Step 1: OIDC authorize (follow redirects)
print("=== Step 1: OIDC authorize ===")
resp = session.get(auth_url, allow_redirects=True, timeout=30)
print(f"  Final URL: {resp.url[:120]}")
print(f"  Status: {resp.status_code}")

# Step 2: Call portal.sso login API
print("\n=== Step 2: portal.sso login API ===")
start_url = resp.url
parsed = urlparse(start_url)
directory_id = ''

# The directory_id might be in the path or query params
# view.awsapps.com/start/ -> the directory is in the hostname or path
# Actually, from the JS code: directory_id comes from window.location.hostname.split(".")[0]
# which would be "view" - but that doesn't make sense
# Looking more carefully: it's the path component
# For us-east-1.signin.aws, the directory is extracted from the path

# Let's call the login API
login_api_url = f"https://portal.sso.us-east-1.amazonaws.com/login"
params = {
    'directory_id': '',  # Will figure out
    'redirect_url': start_url,
}

# Actually, looking at the JS more carefully:
# const b = window.location.hostname.split(".")[0];
# This gets the first part of the hostname. For view.awsapps.com, that's "view"
# But for us-east-1.signin.aws, that would be "us"
# Wait - the JS says:
# if(window.location.pathname.startsWith("/directory/")){ b = window.location.pathname.split("/")[2] }
# So directory_id comes from the path /directory/{id}

# But for the start page, it's just /start/
# The directory_id is likely passed as a query param or extracted from the hostname

# Let me try calling the API without directory_id first
resp2 = session.get(login_api_url, params=params, timeout=30)
print(f"  Status: {resp2.status_code}")
try:
    data = resp2.json()
    print(f"  Response: {json.dumps(data, indent=2)[:500]}")
except:
    print(f"  Response: {resp2.text[:300]}")

# Try with empty directory
print("\n=== Step 2b: Try with directory_id from URL ===")
# The OIDC authorize redirects to view.awsapps.com/start/ with callback_url
# The directory_id might be embedded in the redirect chain

# Let me try following the redirect from the start page manually
resp3 = session.get(auth_url, allow_redirects=False, timeout=30)
print(f"  Auth redirect: {resp3.headers.get('Location', 'NONE')[:120]}")

resp4 = session.get(resp3.headers.get('Location', ''), allow_redirects=False, timeout=30)
print(f"  Start page: {resp4.url[:120]}")
print(f"  Status: {resp4.status_code}")

# Now call the login API with the start page URL
login_params = {
    'directory_id': '',
    'redirect_url': resp4.url,
}
resp5 = session.get(login_api_url, params=login_params, timeout=30)
print(f"\n  Login API status: {resp5.status_code}")
try:
    login_data = resp5.json()
    print(f"  Response: {json.dumps(login_data, indent=2)[:500]}")
    
    redirect_url = login_data.get('redirectUrl', '')
    csrf_token = login_data.get('csrfToken', '')
    print(f"\n  redirectUrl: {redirect_url[:120]}")
    print(f"  csrfToken: {csrf_token[:50]}...")
    
    if redirect_url:
        # Follow the redirect
        print("\n=== Step 3: Follow signin redirect ===")
        resp6 = session.get(redirect_url, allow_redirects=False, timeout=30)
        print(f"  Status: {resp6.status_code}")
        print(f"  Location: {resp6.headers.get('Location', 'NONE')[:120]}")
        
        # If there's another redirect, follow it
        loc = resp6.headers.get('Location', '')
        if loc:
            resp7 = session.get(urljoin(redirect_url, loc), allow_redirects=False, timeout=30)
            print(f"  Final: {resp7.status_code} {resp7.url[:120]}")
            print(f"  Body: {resp7.text[:500]}")
            
            # Save
            with open('/home/ubuntu/kiro-gen/signin_final.html', 'w') as f:
                f.write(resp7.text)
            print("  Saved to signin_final.html")
            
            # Extract form details
            inputs = re.findall(r'<input[^>]*>', resp7.text)
            print(f"\n  Inputs: {len(inputs)}")
            for inp in inputs[:15]:
                print(f"    {inp[:120]}")
            
            # Look for workflowStateHandle
            ws = re.search(r'workflowStateHandle[=:]?\s*["\']?([a-f0-9-]+)', resp7.text)
            if ws:
                print(f"\n  workflowStateHandle: {ws.group(1)}")
                
except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()
