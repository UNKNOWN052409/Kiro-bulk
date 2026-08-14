#!/usr/bin/env python3
"""
Use Playwright to navigate to profile.aws.amazon.com with workflowID
and intercept the API calls to capture exact request format.
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
from urllib.parse import quote

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

email_addr = generate_email()
print(f"Email: {email_addr}")

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

print(f"\n[Browser] Navigating through sign-in flow...")
from playwright.sync_api import sync_playwright

workflow_id = None
captured_api_calls = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    )
    page = browser.new_page()
    
    # Intercept all requests to profile.aws.amazon.com API
    def handle_request(request):
        url = request.url
        if 'profile.aws.amazon.com/api/' in url:
            captured = {
                'url': url,
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': request.post_data
            }
            captured_api_calls.append(captured)
            print(f"  [API] {request.method} {url.split('profile.aws.amazon.com')[1][:60]}")
            if request.post_data:
                try:
                    data = json.loads(request.post_data)
                    # Print without the fingerprint (too long)
                    if 'browserData' in data and 'attributes' in data['browserData']:
                        data['browserData']['attributes']['fingerprint'] = data['browserData']['attributes']['fingerprint'][:50] + '...'
                    print(f"       Body: {json.dumps(data)[:300]}")
                except:
                    print(f"       Body: {request.post_data[:200]}")
    
    page.on('request', handle_request)
    
    try:
        # Navigate to auth URL
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)
        
        # Fill email
        email_input = page.locator('input[type="email"]').first
        email_input.fill(email_addr)
        time.sleep(1)
        
        # Click Continue
        page.locator('button:has-text("Continue")').first.click()
        time.sleep(5)
        
        # Click Sign up / Get started
        for selector in ['button:has-text("Sign up")', 'button:has-text("Create account")', 'button:has-text("Get started")']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click()
                    print(f"  Clicked: {selector}")
                    break
            except:
                pass
        
        time.sleep(5)
        print(f"  URL: {page.url[:120]}")
        
        # Wait for profile.aws.amazon.com
        for i in range(10):
            time.sleep(1)
            url = page.url
            if 'profile.aws.amazon.com' in url and 'workflowID=' in url:
                raw = url.split('workflowID=')[1]
                workflow_id = raw.split('#')[0].split('&')[0]
                if re.match(r'[0-9a-f-]{36}$', workflow_id):
                    print(f"  FOUND workflowID: {workflow_id}")
                    break
        
        # Wait for API calls to complete
        time.sleep(10)
        
        browser.close()
    except Exception as e:
        print(f"  Error: {e}")
        browser.close()

print(f"\n{'='*60}")
print(f"Captured {len(captured_api_calls)} API calls:")
print(f"{'='*60}")

for i, call in enumerate(captured_api_calls):
    print(f"\n[{i}] {call['method']} {call['url'].split('profile.aws.amazon.com')[1][:80]}")
    print(f"    Headers: {json.dumps({k: v for k, v in call['headers'].items() if k.lower() in ['content-type', 'origin', 'referer', 'accept', 'x-requested-with', 'authorization']})[:200]}")
    if call['post_data']:
        try:
            data = json.loads(call['post_data'])
            # Truncate fingerprint
            if 'browserData' in data:
                bd = data['browserData']
                if 'attributes' in bd and 'fingerprint' in bd['attributes']:
                    bd['attributes']['fingerprint'] = bd['attributes']['fingerprint'][:30] + f"...({len(bd['attributes']['fingerprint'])} chars)"
                if 'cookies' in bd:
                    bd['cookies'] = bd['cookies'][:2] if len(bd['cookies']) > 2 else bd['cookies']
            print(f"    Body: {json.dumps(data, indent=2)[:800]}")
        except:
            print(f"    Body: {call['post_data'][:300]}")

# Save the captured calls
with open('/home/ubuntu/kiro-gen/profile_api_calls.json', 'w') as f:
    json.dump(captured_api_calls, f, indent=2)

print(f"\nSaved to profile_api_calls.json")
