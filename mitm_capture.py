#!/usr/bin/env python3
"""
MITM-based request interception for AWS OIDC flow.
Captures ALL network requests to understand the exact API endpoints,
headers, and body formats used during account creation.
"""

from playwright.sync_api import sync_playwright
from cloakbrowser import launch
import time, uuid, secrets, hashlib, base64, requests, random, string, json

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

# Register OIDC client
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9991/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

# PKCE
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = 'http://127.0.0.1:9991/oauth/callback'
auth_url = f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scopes={scopes_encoded}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256'

email = generate_email()
name = "Vikram Singh"

print(f"Email: {email}")
print(f"Capturing network requests...")
print("="*80)

captured_requests = []

def on_request(request):
    url = request.url
    method = request.method
    headers = request.headers
    post_data = request.post_data
    
    # Only capture interesting requests (not static assets)
    interesting = False
    for domain in ['profile.aws', 'signin.aws', 'oidc', 'awsapps', 'cognito', 'amazon']:
        if domain in url:
            interesting = True
            break
    
    if interesting:
        entry = {
            'method': method,
            'url': url,
            'headers': dict(headers),
            'post_data': post_data,
            'timestamp': time.time()
        }
        captured_requests.append(entry)
        
        # Print POST requests with full details
        if method == 'POST':
            print(f"\n[POST] {url}")
            print(f"  Headers: {json.dumps({k:v for k,v in headers.items() if k.lower() not in ['host', 'content-length', 'sec-ch-ua-platform']}, indent=2)[:500]}")
            if post_data:
                print(f"  Body: {post_data[:500]}")
            print("-"*60)

browser = launch(headless=False, humanize=True)
page = browser.new_page()

# Set up request interception
page.on("request", on_request)

# Navigate to auth URL
page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)

# Wait for sign-in page
for i in range(15):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            if 'email' in body.lower() and 'continue' in body.lower():
                break
        except:
            pass

# Enter email
print("\n--- Entering email ---")
inputs = page.locator('input').all()
visible = [inp for inp in inputs if inp.is_visible()]
email_inp = None
for inp in visible:
        inp_type = inp.get_attribute('type') or 'text'
        if inp_type in ('email', 'text'):
            email_inp = inp
            break
if email_inp is None and visible:
        email_inp = visible[0]
email_inp.fill(email)
time.sleep(2)
btn = page.get_by_role("button", name="Continue", exact=True).first
btn.click()

# Wait a bit for requests to complete
time.sleep(5)

# Wait for Name page
print("\n--- Waiting for Name page ---")
for i in range(30):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            url = page.url
            if 'enter your name' in body.lower():
                print(f"Name page loaded! URL: {url}")
                break
        except:
            pass

# Enter name
print("\n--- Entering name ---")
name_inputs = page.locator('input[type="text"]').all()
visible_name = [inp for inp in name_inputs if inp.is_visible()]
if visible_name:
        visible_name[0].fill(name)
        time.sleep(2)
        btn = page.get_by_role("button", name="Continue", exact=True).first
        btn.click()

# Wait for POST requests
time.sleep(10)

# Check what happened
body = page.evaluate("() => document.body ? document.body.innerText : ''")
print(f"\nFinal body: {body[:200]}")

# Save all captured requests
with open('/home/ubuntu/kiro-gen/captured_requests.json', 'w') as f:
        json.dump(captured_requests, f, indent=2)

print(f"\nTotal captured requests: {len(captured_requests)}")
print(f"Saved to captured_requests.json")

browser.close()
