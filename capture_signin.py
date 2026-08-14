"""
Capture the signin.aws page HTML and analyze the form structure.
"""

import uuid, secrets, hashlib, base64, requests, json, re
from urllib.parse import quote, urlparse, parse_qs, urljoin

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
session.headers.update({
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})

# Follow the full redirect chain
resp = session.get(auth_url, allow_redirects=True, timeout=30)
start_url = resp.url
print(f"Start URL: {start_url[:80]}")

# Call portal.sso login API
resp2 = session.get(
    'https://portal.sso.us-east-1.amazonaws.com/login',
    params={'directory_id': 'view', 'redirect_url': start_url},
    timeout=30
)
login_data = resp2.json()
redirect_url = login_data['redirectUrl']
csrf_token = login_data['csrfToken']
print(f"\nredirectUrl: {redirect_url}")
print(f"csrfToken: {csrf_token}")

# Set the CSRF cookie
from urllib.parse import urlparse as up
parsed = up(redirect_url)
cookie_path = '/'
session.cookies.set('loginCsrfToken', csrf_token, domain='.signin.aws', path=cookie_path)

# Follow the redirect to signin.aws
resp3 = session.get(redirect_url, allow_redirects=True, timeout=30)
print(f"\nSignin page: {resp3.status_code} ({len(resp3.text)} bytes)")
print(f"Final URL: {resp3.url[:120]}")

# Save HTML
with open('/home/ubuntu/kiro-gen/signin_page.html', 'w') as f:
    f.write(resp3.text)
print("Saved to signin_page.html")

# Analyze the HTML
print("\n=== HTML Analysis ===")

# Check if it's a SPA (React) or static HTML
if '<div id="root"' in resp3.text or 'react' in resp3.text.lower():
    print("It's a React SPA")
    
# Look for script tags
scripts = re.findall(r'<script[^>]*src="([^"]+)"', resp3.text)
print(f"\nScripts: {scripts[:10]}")

# Look for inline scripts
inline_scripts = re.findall(r'<script[^>]*>(.*?)</script>', resp3.text, re.DOTALL)
print(f"\nInline scripts: {len(inline_scripts)}")
for i, s in enumerate(inline_scripts[:5]):
    print(f"  Script {i}: {s[:200]}")

# Look for API endpoints in JS
api_eps = set()
for s in inline_scripts:
    eps = re.findall(r'["\'](/api/[^"\']+)["\']', s)
    api_eps.update(eps)
print(f"\nAPI endpoints in inline JS: {api_eps}")

# Look for form-related patterns
form_patterns = re.findall(r'(?:fetch|axios|XMLHttpRequest)\(["\']([^"\']+)["\']', resp3.text)
print(f"\nFetch/XHR patterns: {form_patterns[:10]}")

# Look for POST endpoints
post_eps = re.findall(r'method:\s*["\']POST["\'][^}]*url:\s*["\']([^"\']+)["\']', resp3.text)
print(f"\nPOST endpoints: {post_eps[:5]}")

# Look for the login form structure
# The signin.aws uses a state machine with workflowStateHandle
# The email is typically submitted via a POST to /platform/{dir}/login

# Check for the workflowStateHandle
ws = re.search(r'workflowStateHandle=([a-f0-9-]+)', resp3.url)
if ws:
    print(f"\nworkflowStateHandle in URL: {ws.group(1)}")

# Look for any form elements (even in SPA, there might be noscript fallback)
forms = re.findall(r'<form[^>]*>', resp3.text)
print(f"\nForms: {len(forms)}")
for f in forms[:5]:
    print(f"  {f[:150]}")

inputs = re.findall(r'<input[^>]*>', resp3.text)
print(f"\nInputs: {len(inputs)}")
for inp in inputs[:10]:
    print(f"  {inp[:150]}")

# The SPA might have a different structure. Let's look for the JS bundle
# that handles the login
for script_url in scripts:
    if 'main' in script_url or 'app' in script_url:
        print(f"\nFetching JS bundle: {script_url}")
        try:
            js_resp = session.get(urljoin(resp3.url, script_url), timeout=30)
            js_text = js_resp.text
            print(f"  JS size: {len(js_text)}")
            
            # Look for API endpoints in the JS
            js_api_eps = re.findall(r'["\'](/api/[^"\']+)["\']', js_text)
            print(f"  API endpoints in JS: {js_api_eps[:15]}")
            
            # Look for login-related endpoints
            login_eps = [ep for ep in js_api_eps if 'login' in ep or 'auth' in ep or 'session' in ep]
            print(f"  Login-related: {login_eps[:10]}")
            
            # Save JS for analysis
            with open('/home/ubuntu/kiro-gen/signin_main.js', 'w') as f:
                f.write(js_text)
            print("  Saved to signin_main.js")
            
        except Exception as e:
            print(f"  Error: {e}")
