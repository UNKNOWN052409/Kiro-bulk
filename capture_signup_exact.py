"""Use Playwright to navigate through the sign-in flow and capture the EXACT signup API call"""
import os
os.environ['DISPLAY'] = ':99'

from playwright.sync_api import sync_playwright
import json, time, uuid, random, re
from urllib.parse import quote, urlparse

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
CALLBACK_PORT = 9997
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis"]
ISSUER_URL = 'https://view.awsapps.com/start'

email = f"test{uuid.uuid4().hex[:8]}@havenhaus.in"

# Register OIDC client
import requests as req
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code"],
    "redirectUris": [f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = req.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

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

print(f"Client ID: {client_id}")
print(f"Email: {email}")

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path='/usr/bin/chromium',
        headless=False,
        args=[
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--window-size=1920,1080',
            '--use-mock-keychain',
        ]
    )
    
    page = browser.new_page()
    
    # Capture all network requests
    captured_requests = []
    
    def on_request(request):
        captured_requests.append({
            'url': request.url,
            'method': request.method,
            'headers': dict(request.headers),
            'post_data': request.post_data
        })
    
    page.on('request', on_request)
    
    print("\n[1] Navigating to OIDC authorize...")
    page.goto(auth_url, wait_until='commit', timeout=30000)
    
    # Wait for JS redirects to happen naturally (view.awsapps.com -> portal.sso -> signin.aws)
    print("    Waiting for JS redirects...")
    for i in range(20):
        url = page.url
        if 'signin.aws' in url and 'workflowStateHandle' in url:
            print(f"    Reached signin.aws at step {i}")
            break
        elif 'portal.sso' in url:
            print(f"    On portal.sso at step {i}, waiting...")
        elif 'view.awsapps' in url:
            print(f"    On view.awsapps at step {i}, waiting...")
        else:
            print(f"    Unknown URL at step {i}: {url[:80]}")
        time.sleep(2)
    
    print(f"    Final URL: {page.url[:100]}...")
    
    # Check if we're on the login page
    if 'signin.aws' in page.url and 'workflowStateHandle' in page.url:
        wsh = page.url.split('workflowStateHandle=')[1].split('&')[0]
        print(f"    WSH: {wsh}")
        
        # Wait for SPA to render the form
        print("    Waiting for SPA to render login form...")
        time.sleep(8)
        
        # Check page content
        content = page.content()
        print(f"    Content length: {len(content)}")
        
        # Look for email input
        email_input = page.query_selector('input[type="email"], input[name="username"], input[id="usernameInput"], input')
        if email_input:
            print(f"    Found email input!")
            email_input.fill(email)
            time.sleep(random.uniform(1, 2))
            
            # Click Continue
            continue_btn = page.query_selector('button[type="submit"], #nextButton, [data-testid="test-primary-button"], button:has-text("Continue")')
            if continue_btn:
                print("    Clicking Continue...")
                continue_btn.click()
                time.sleep(5)
                print(f"    URL after email: {page.url[:100]}...")
                
                time.sleep(3)
                
                # Look for "Sign up" button/link
                signup_el = None
                for selector in [
                    'a:has-text("Sign up")',
                    'button:has-text("Sign up")',
                    'a:has-text("Create account")',
                    'button:has-text("Create account")',
                    '[data-testid="test-create-account-link"]',
                ]:
                    try:
                        signup_el = page.query_selector(selector)
                        if signup_el:
                            print(f"    Found signup via: {selector}")
                            break
                    except:
                        pass
                
                if signup_el:
                    print(f"    Clicking signup...")
                    signup_el.click()
                    time.sleep(8)
                    print(f"    URL after signup: {page.url[:100]}...")
                else:
                    print("    No signup element found")
                    # Maybe the page already shows the profile page
                    if 'profile.aws' in page.url:
                        print("    Already on profile page!")
        else:
            print("    No email input found")
            print(f"    Page title: {page.title()}")
            print(f"    Content snippet: {content[:500]}")
    else:
        print(f"    Not on signin.aws login page")
        print(f"    URL: {page.url[:100]}")
    
    # Save captured requests
    print(f"\nCaptured {len(captured_requests)} requests")
    for i, r in enumerate(captured_requests):
        if r['method'] == 'POST':
            print(f"  [{i}] {r['method']} {r['url'][:80]}")
            if r['post_data']:
                try:
                    data = json.loads(r['post_data'])
                    print(f"       stepId={data.get('stepId','')}, actionId={data.get('actionId','')}")
                    print(f"       WSH={data.get('workflowStateHandle','')[:8]}...")
                    print(f"       Cookie: {r['headers'].get('Cookie', 'none')}")
                    print(f"       Origin: {r['headers'].get('Origin', 'none')}")
                    print(f"       Referer: {r['headers'].get('Referer', 'none')}")
                    print(f"       Full headers: {json.dumps(r['headers'], indent=2)}")
                except:
                    pass
    
    with open('/home/ubuntu/kiro-gen/captured_signup_exact.json', 'w') as f:
        json.dump(captured_requests, f, indent=2)
    
    print("\nDone!")
    browser.close()
