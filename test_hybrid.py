#!/usr/bin/env python3
"""
Hybrid approach:
1. Use browser (no proxy) for redirect chain + email + signup to get profile URL
2. Switch to API calls (with proxy) for profile.aws.amazon.com APIs

The key insight: the browser navigates to profile.aws.amazon.com/?workflowID=UUID
after the signup. We need to capture that URL before the SPA tries to render.
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
from urllib.parse import quote

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

email_addr = generate_email()
print(f"Email: {email_addr}")

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
print(f"Client ID: {client_id[:16]}...")

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

# Use browser (no proxy) to get through the sign-in flow and capture the profile URL
print("\n[Browser] Navigating through sign-in flow...")
from playwright.sync_api import sync_playwright

workflow_id = None
wsh_from_signup = None

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    )
    page = browser.new_page()
    
    try:
        # Navigate to auth URL
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        print(f"  URL after goto: {page.url[:100]}")
        
        # Wait for sign-in page
        for i in range(10):
            time.sleep(2)
            url = page.url
            if 'workflowStateHandle=' in url:
                wsh = url.split('workflowStateHandle=')[1].split('&')[0]
                print(f"  Got WSH: {wsh}")
                break
        
        # Wait for sign-in page to load
        time.sleep(3)
        print(f"  Page title: {page.title()}")
        
        # Try to find and fill email
        email_input = None
        for selector in ['input[type="email"]', 'input[name="username"]', 'input[placeholder*="email"]', 'input[placeholder*="Email"]']:
            try:
                email_input = page.locator(selector).first
                if email_input.is_visible():
                    email_input.fill(email_addr)
                    print(f"  Email filled using: {selector}")
                    break
            except:
                pass
        
        if email_input is None:
            print("  ERROR: Could not find email input")
            browser.close()
            raise Exception("Could not find email input")
        
        time.sleep(1)
        
        # Click Continue/Submit
        clicked = False
        for selector in ['button[type="submit"]', 'button:has-text("Continue")', 'button:has-text("Sign in")', '#submitButton']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click()
                    print(f"  Clicked: {selector}")
                    clicked = True
                    break
            except:
                pass
        
        if not clicked:
            print("  ERROR: Could not find submit button")
            browser.close()
            raise Exception("Could not find submit button")
        
        time.sleep(5)
        print(f"  URL after email submit: {page.url[:120]}")
        
        # Check if we're on the name page (profile.aws.amazon.com)
        # or if we need to click "Sign up" / "Create account"
        if 'profile.aws.amazon.com' in page.url:
            if 'workflowID=' in page.url:
                workflow_id = page.url.split('workflowID=')[1].split('&')[0]
                print(f"  FOUND workflowID: {workflow_id}")
            else:
                print(f"  On profile page but no workflowID yet: {page.url[:100]}")
        else:
            # We might be on a "Get started" or "Sign up" page
            # Try to find and click signup button
            for selector in ['button:has-text("Sign up")', 'button:has-text("Create account")', 'button:has-text("Get started")', 'a:has-text("Sign up")']:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        btn.click()
                        print(f"  Clicked signup: {selector}")
                        break
                except:
                    pass
            
            time.sleep(5)
            print(f"  URL after signup click: {page.url[:120]}")
        
        # Wait for redirect to profile.aws.amazon.com
        for i in range(20):
            time.sleep(1)
            url = page.url
            if i < 5 or 'profile.aws' in url:
                print(f"  [{i}] URL: {url[:100]}")
            
            if 'profile.aws.amazon.com' in url and 'workflowID=' in url:
                # Extract just the UUID part (before # or &)
                raw = url.split('workflowID=')[1]
                workflow_id = raw.split('#')[0].split('&')[0]
                # Ensure it's a valid UUID format
                if re.match(r'[0-9a-f-]{36}$', workflow_id):
                    print(f"  FOUND workflowID: {workflow_id}")
                    break
        
        browser.close()
    except Exception as e:
        print(f"  Browser error: {e}")
        browser.close()

if workflow_id:
    print(f"\n[API] Switching to API calls with proxy...")
    
    # Create API session with proxy
    session = requests.Session()
    proxy_url = f"socks5://api-US:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
    session.proxies = {'http': proxy_url, 'https': proxy_url}
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://profile.aws.amazon.com',
        'Referer': f'https://profile.aws.amazon.com/?workflowID={workflow_id}',
    })
    
    # Use correct headers (no Origin, no Accept, just Referer and Content-Type)
    profile_headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Referer': f'https://profile.aws.amazon.com/?workflowID={workflow_id}',
    }
    
    # get-config
    print("  Calling /api/get-config...")
    config_resp = session.post('https://profile.aws.amazon.com/api/get-config', 
                               json={}, headers=profile_headers, timeout=30)
    print(f"  Config: HTTP {config_resp.status_code}")
    
    # get-app-context
    print("  Calling /api/get-app-context...")
    ctx_resp = session.post('https://profile.aws.amazon.com/api/get-app-context', 
                           json={"workflowID": workflow_id}, headers=profile_headers, timeout=30)
    print(f"  Context: HTTP {ctx_resp.status_code}")
    print(f"  Context response: {ctx_resp.text[:300]}")
    
    # start - with correct format
    print("  Calling /api/start...")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"
    
    start_payload = {
        "workflowID": workflow_id,
        "browserData": {
            "attributes": {
                "fingerprint": PROFILE_FP,
                "eventTimestamp": now,
                "timeSpentOnPage": "44",
                "eventType": "PageLoad",
                "ubid": f"{random.randint(100,999)}-{random.randint(1000000,9999999)}-{random.randint(1000000,9999999)}"
            },
            "cookies": {}
        }
    }
    
    start_resp = session.post('https://profile.aws.amazon.com/api/start', 
                              json=start_payload, headers=profile_headers, timeout=30)
    print(f"  Start: HTTP {start_resp.status_code}")
    print(f"  Start response: {start_resp.text[:500]}")
    
    if start_resp.status_code == 200:
        data = start_resp.json()
        print(f"  Response keys: {list(data.keys())}")
        workflow_state = data.get('workflowState') or data.get('state')
        print(f"  workflowState: {workflow_state}")
        
        if workflow_state:
            # send-otp
            print("  Calling /api/send-otp...")
            otp_payload = {
                "workflowState": workflow_state,
                "email": email_addr,
                "browserData": {
                    "attributes": {
                        "fingerprint": PROFILE_FP,
                        "eventTimestamp": now,
                        "timeSpentOnPage": "10",
                        "eventType": "OTPRequest",
                        "ubid": start_payload['browserData']['attributes']['ubid']
                    },
                    "cookies": {}
                }
            }
            otp_resp = session.post('https://profile.aws.amazon.com/api/send-otp', 
                                   json=otp_payload, headers=profile_headers, timeout=30)
            print(f"  Send OTP: HTTP {otp_resp.status_code}")
            print(f"  Response: {otp_resp.text[:300]}")
    else:
        print(f"  Could not start workflow")
else:
    print("ERROR: Could not get workflowID from browser")

print(f"\n{'='*60}")
