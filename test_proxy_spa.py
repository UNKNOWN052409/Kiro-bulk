#!/usr/bin/env python3
"""
Test: Use proxy for ALL traffic including profile.aws.amazon.com
Wait 60+ seconds for the SPA to load.
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
from urllib.parse import quote

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'

FIRST_NAMES = ["James", "Sarah", "Michael", "Emma", "David", "Olivia", "Daniel", "Sophia", "Matthew", "Isabella"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

def generate_account():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{prefix}@havenhaus.in"
    return first, last, email

first_name, last_name, email_addr = generate_account()
full_name = f"{first_name} {last_name}"
print(f"Account: {full_name} <{email_addr}>")

# Register OIDC client (no proxy)
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

print(f"\n[Browser with proxy] Navigating through sign-in flow...")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage'],
        proxy={
            'server': f'socks5://127.0.0.1:10800',
            'bypass': '<-loopback>,*.amazonaws.com,*.awsapps.com,*.signin.aws,*.amazon.com,oidc.*'
        }
    )
    page = browser.new_page()
    
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
        workflow_id = None
        for i in range(10):
            time.sleep(1)
            url = page.url
            if 'profile.aws.amazon.com' in url and 'workflowID=' in url:
                raw = url.split('workflowID=')[1]
                workflow_id = raw.split('#')[0].split('&')[0]
                if re.match(r'[0-9a-f-]{36}$', workflow_id):
                    print(f"  workflowID: {workflow_id}")
                    break
        
        if not workflow_id:
            print("  ERROR: No workflowID found")
            browser.close()
            raise Exception("No workflowID")
        
        # Wait for SPA to load (LONG wait)
        print(f"\n[SPA] Waiting for profile.aws.amazon.com SPA to load through proxy...")
        spa_loaded = False
        for i in range(30):  # 60 seconds max
            time.sleep(2)
            try:
                body_text = page.inner_text('body')
                html_len = len(page.content())
                if i % 5 == 0:
                    print(f"  [{i*2}s] body_text_len={len(body_text)}, html_len={html_len}")
                
                if len(body_text) > 100:
                    print(f"  SPA loaded after {i*2}s!")
                    print(f"  Body: {body_text[:200]}")
                    spa_loaded = True
                    break
            except:
                pass
        
        if not spa_loaded:
            print("  SPA did not load through proxy")
            browser.close()
            raise Exception("SPA did not load")
        
        # Fill name
        print(f"\n[Name] Filling: {full_name}")
        try:
            name_input = page.locator('input[type="text"][placeholder]').first
            name_input.click()
            time.sleep(0.5)
            for char in full_name:
                name_input.type(char, delay=random.uniform(50, 150))
            time.sleep(1)
            print(f"  Name filled")
        except Exception as e:
            print(f"  Error: {e}")
        
        # Click Continue
        print(f"\n[Continue] Clicking...")
        try:
            page.locator('button:has-text("Continue")').first.click()
            print("  Continue clicked")
        except Exception as e:
            print(f"  Error: {e}")
        
        # Wait for next page
        time.sleep(5)
        print(f"  URL: {page.url[:120]}")
        
        try:
            body_text = page.inner_text('body')
            print(f"  Body: {body_text[:300]}")
        except:
            pass
        
        browser.close()
    except Exception as e:
        print(f"  Error: {e}")
        browser.close()

print(f"\n{'='*60}")
