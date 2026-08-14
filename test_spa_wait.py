#!/usr/bin/env python3
"""
Wait for the profile.aws.amazon.com SPA to fully load,
then capture its API calls and responses.
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
api_responses = {}
captured_requests = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    )
    page = browser.new_page()
    
    # Capture API responses
    def handle_response(response):
        url = response.url
        if 'profile.aws.amazon.com/api/' in url:
            try:
                body = response.text()
                captured_requests.append({
                    'url': url.split('profile.aws.amazon.com')[1],
                    'status': response.status,
                    'body': body[:500]
                })
                print(f"  [RESP] {response.status} {url.split('profile.aws.amazon.com')[1][:50]}")
                if len(body) > 10:
                    print(f"         Body: {body[:200]}")
            except:
                pass
    
    page.on('response', handle_response)
    
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
        
        # Click Sign up
        for selector in ['button:has-text("Sign up")', 'button:has-text("Create account")', 'button:has-text("Get started")']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click()
                    print(f"  Clicked: {selector}")
                    break
            except:
                pass
        
        time.sleep(3)
        
        # Wait for profile.aws.amazon.com with workflowID
        for i in range(10):
            time.sleep(1)
            url = page.url
            if 'profile.aws.amazon.com' in url and 'workflowID=' in url:
                raw = url.split('workflowID=')[1]
                workflow_id = raw.split('#')[0].split('&')[0]
                if re.match(r'[0-9a-f-]{36}$', workflow_id):
                    print(f"  FOUND workflowID: {workflow_id}")
                    break
        
        if workflow_id:
            print(f"\n[SPA] Waiting for profile.aws.amazon.com SPA to load...")
            print(f"  Current URL: {page.url[:100]}")
            
            # Wait for SPA to load - check body content
            for i in range(30):
                time.sleep(2)
                try:
                    body_text = page.inner_text('body')
                    html_len = len(page.content())
                    if i % 5 == 0:
                        print(f"  [{i*2}s] body_text_len={len(body_text)}, html_len={html_len}")
                    
                    # If body has content, SPA has loaded
                    if len(body_text) > 100:
                        print(f"  SPA loaded! body_text: {body_text[:200]}")
                        break
                except:
                    pass
            
            # Now check what the SPA rendered
            try:
                body_text = page.inner_text('body')
                html = page.content()
                print(f"\n  Final body_text_len: {len(body_text)}")
                print(f"  Final html_len: {len(html)}")
                print(f"  Body preview: {body_text[:300]}")
                
                # Check if there's a form (name input)
                inputs = page.query_selector_all('input')
                print(f"  Number of inputs: {len(inputs)}")
                for inp in inputs:
                    try:
                        name = inp.get_attribute('name')
                        placeholder = inp.get_attribute('placeholder')
                        input_type = inp.get_attribute('type')
                        print(f"    input: type={input_type}, name={name}, placeholder={placeholder}")
                    except:
                        pass
                
                # Check for any visible buttons
                buttons = page.query_selector_all('button')
                print(f"  Number of buttons: {len(buttons)}")
                for btn in buttons:
                    try:
                        text = btn.inner_text()
                        visible = btn.is_visible()
                        if visible:
                            print(f"    visible button: '{text}'")
                    except:
                        pass
                        
            except Exception as e:
                print(f"  Error checking SPA: {e}")
        
        browser.close()
    except Exception as e:
        print(f"  Error: {e}")
        browser.close()

print(f"\n{'='*60}")
print(f"Captured API responses: {len(captured_requests)}")
for req in captured_requests:
    print(f"  {req['status']} {req['url'][:60]}")
    if req['body']:
        print(f"    {req['body'][:100]}")
