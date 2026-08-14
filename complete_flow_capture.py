#!/usr/bin/env python3
"""
Complete account creation flow WITHOUT proxy.
Captures ALL network requests to understand the full API format.
This prepares everything so that when a working proxy is provided,
we just plug it in.
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time, os, sys
from urllib.parse import quote, urlparse

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

FIRST_NAMES = ["Aditya", "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Karan", "Deepika", "Arjun", 
               "Meera", "Rohan", "Kavya", "Nikhil", "Divya", "Siddharth", "Pooja", "Vishal", "Ritu", "Aman",
               "James", "Sarah", "Michael", "Emma", "David", "Olivia", "Daniel", "Sophia", "Matthew", "Isabella",
               "Christopher", "Mia", "Andrew", "Charlotte", "Joshua", "Amelia", "Ryan", "Harper", "Brandon", "Evelyn"]
LAST_NAMES = ["Sharma", "Patel", "Singh", "Kumar", "Gupta", "Verma", "Mehta", "Agarwal", "Joshi", "Reddy",
              "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Anderson", "Taylor", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Moore", "Clark"]

def generate_account():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{prefix}@havenhaus.in"
    return first, last, email

def generate_password():
    chars = string.ascii_letters + string.digits + "!@#$%"
    length = random.randint(12, 16)
    password = ''.join(random.choices(chars, k=length))
    # Ensure at least one uppercase, lowercase, digit, special
    if not any(c.isupper() for c in password):
        password = password[:-1] + random.choice(string.ascii_uppercase)
    if not any(c.islower() for c in password):
        password = password[:-2] + random.choice(string.ascii_lowercase) + password[-1]
    if not any(c.isdigit() for c in password):
        password = password[:-3] + random.choice(string.digits) + password[-2:]
    return password

email_addr = None
account_data = {}
all_requests = []
all_responses = []

print("="*70)
print("Kiro Account Creation - Complete Flow Capture (No Proxy)")
print("="*70)

# Generate account
first_name, last_name, email_addr = generate_account()
full_name = f"{first_name} {last_name}"
password = generate_password()
account_data = {'first': first_name, 'last': last_name, 'email': email_addr, 'password': password}
print(f"\nAccount: {full_name} <{email_addr}>")
print(f"Password: {password}")

# Register OIDC client
print(f"\n[0] Registering OIDC client...")
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
print(f"    Client ID: {client_id}")

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

# Start browser
print(f"\n[1] Starting browser...")
from playwright.sync_api import sync_playwright

# Token capture server
tokens_captured = {}

def start_token_server():
    """Start a simple HTTP server to catch OAuth callback"""
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if '/oauth/callback' in self.path:
                parsed = urlparse(self.path)
                params = dict(p.split('=', 1) for p in parsed.query.split('&') if '=' in p)
                code = params.get('code', '')
                captured_state = params.get('state', '')
                if code:
                    tokens_captured['code'] = code
                    tokens_captured['state'] = captured_state
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<html><body><h1>Auth Complete!</h1></body></html>')
                    return
            self.send_response(404)
            self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Suppress logging
    
    server = HTTPServer(('127.0.0.1', 9997), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

token_server = start_token_server()
print(f"    Token callback server started on :9997")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    )
    page = browser.new_page()
    
    # Capture all requests
    def handle_request(request):
        url = request.url
        method = request.method
        post_data = request.post_data
        all_requests.append({
            'url': url,
            'method': method,
            'headers': dict(request.headers),
            'post_data': post_data,
            'timestamp': time.time()
        })
    
    def handle_response(response):
        url = response.url
        if 'signin.aws' in url or 'profile.aws' in url or 'awsapps.com' in url:
            try:
                body = response.text()
                all_responses.append({
                    'url': url,
                    'status': response.status,
                    'body': body[:2000],
                    'timestamp': time.time()
                })
            except:
                pass
    
    page.on('request', handle_request)
    page.on('response', handle_response)
    
    try:
        # Navigate to auth URL
        print(f"\n[2] Navigating to OIDC authorize...")
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)
        print(f"    URL: {page.url[:100]}")
        
        # Fill email
        print(f"\n[3] Entering email: {email_addr}")
        email_input = page.locator('input[type="email"]').first
        email_input.click()
        time.sleep(0.3)
        for char in email_addr:
            email_input.type(char, delay=random.uniform(30, 80))
        time.sleep(1)
        
        # Click Continue
        print(f"    Clicking Continue...")
        page.locator('button:has-text("Continue")').first.click()
        time.sleep(5)
        print(f"    URL: {page.url[:120]}")
        
        # Click Sign up
        print(f"\n[4] Looking for Sign up button...")
        for selector in ['button:has-text("Sign up")', 'button:has-text("Create account")', 'button:has-text("Get started")']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click()
                    print(f"    Clicked: {selector}")
                    break
            except:
                pass
        
        time.sleep(3)
        print(f"    URL: {page.url[:120]}")
        
        # Wait for profile.aws.amazon.com with workflowID
        workflow_id = None
        for i in range(15):
            time.sleep(1)
            url = page.url
            if 'profile.aws.amazon.com' in url and 'workflowID=' in url:
                raw = url.split('workflowID=')[1]
                workflow_id = raw.split('#')[0].split('&')[0]
                if re.match(r'[0-9a-f-]{36}$', workflow_id):
                    print(f"    workflowID: {workflow_id}")
                    break
        
        if not workflow_id:
            print("    ERROR: No workflowID found")
            raise Exception("No workflowID")
        
        # Wait for SPA to load
        print(f"\n[5] Waiting for SPA to load...")
        for i in range(30):
            time.sleep(2)
            try:
                body_text = page.inner_text('body')
                if len(body_text) > 100:
                    print(f"    SPA loaded after {i*2}s")
                    print(f"    Body: {body_text[:200]}")
                    break
            except:
                pass
        
        # Fill name
        print(f"\n[6] Filling name: {full_name}")
        try:
            name_input = page.locator('input[type="text"][placeholder]').first
            name_input.click()
            time.sleep(0.5)
            for char in full_name:
                name_input.type(char, delay=random.uniform(50, 150))
                time.sleep(random.uniform(0.01, 0.03))
            time.sleep(1)
            print(f"    Name filled")
        except Exception as e:
            print(f"    Error filling name: {e}")
            raise
        
        # Click Continue (submit name)
        print(f"\n[7] Submitting name...")
        page.locator('button:has-text("Continue")').first.click()
        time.sleep(3)
        print(f"    URL: {page.url[:120]}")
        
        try:
            body_text = page.inner_text('body')
            print(f"    Body: {body_text[:300]}")
        except:
            pass
        
        # Check for OTP page
        if 'otp' in page.url.lower() or 'verification' in page.url.lower() or 'Enter the code' in page.inner_text('body'):
            print(f"\n[8] OTP page detected!")
            body_text = page.inner_text('body')
            print(f"    Body: {body_text[:300]}")
            
            # Get OTP from Gmail
            from extract_otp_v3 import get_latest_otp
            otp = get_latest_otp(email_addr, timeout=120)
            print(f"    OTP: {otp}")
            
            if otp:
                # Fill OTP
                otp_input = page.locator('input[type="text"][placeholder*="code"], input[placeholder*="Code"], input[name*="otp"], input[id*="otp"]').first
                otp_input.click()
                time.sleep(0.5)
                for char in otp:
                    otp_input.type(char, delay=random.uniform(50, 100))
                time.sleep(1)
                
                # Click Continue
                page.locator('button:has-text("Continue"), button:has-text("Verify"), button:has-text("Submit")').first.click()
                time.sleep(5)
                print(f"    URL after OTP: {page.url[:120]}")
        else:
            print(f"\n[8] Not on OTP page. Current state:")
            print(f"    URL: {page.url[:120]}")
        
        # Check for password page
        body_text = page.inner_text('body')
        print(f"\n[9] Current body: {body_text[:300]}")
        
        if 'password' in body_text.lower() or 'Password' in body_text:
            print(f"    Password page detected!")
            # Fill password
            pwd_inputs = page.query_selector_all('input[type="password"]')
            if len(pwd_inputs) >= 2:
                pwd_inputs[0].click()
                time.sleep(0.5)
                for char in password:
                    pwd_inputs[0].type(char, delay=random.uniform(30, 80))
                time.sleep(0.5)
                pwd_inputs[1].click()
                time.sleep(0.5)
                for char in password:
                    pwd_inputs[1].type(char, delay=random.uniform(30, 80))
            elif len(pwd_inputs) == 1:
                pwd_inputs[0].click()
                time.sleep(0.5)
                for char in password:
                    pwd_inputs[0].type(char, delay=random.uniform(30, 80))
            time.sleep(1)
            print(f"    Password filled")
            
            # Click Continue
            page.locator('button:has-text("Continue"), button:has-text("Create account")').first.click()
            time.sleep(5)
            print(f"    URL after password: {page.url[:120]}")
        
        # Check for Allow page
        body_text = page.inner_text('body')
        print(f"\n[10] Current body: {body_text[:300]}")
        
        if 'Allow' in body_text or 'allow' in body_text.lower():
            print(f"    Allow page detected!")
            # Click Allow
            try:
                allow_btn = page.locator('button:has-text("Allow")').first
                allow_btn.click()
                print(f"    Allow clicked")
                time.sleep(3)
            except:
                # Try clicking "Confirm and continue" first
                try:
                    page.locator('button:has-text("Confirm and continue")').first.click()
                    time.sleep(3)
                    page.locator('button:has-text("Allow")').first.click()
                    print(f"    Two-step Allow clicked")
                    time.sleep(3)
                except Exception as e:
                    print(f"    Error on Allow page: {e}")
        
        # Wait for token
        print(f"\n[11] Waiting for token...")
        for i in range(30):
            time.sleep(1)
            if 'code' in tokens_captured:
                code = tokens_captured['code']
                print(f"    Got auth code: {code[:20]}...")
                
                # Exchange code for tokens
                token_resp = requests.post(f'{OIDC_BASE}/token', json={
                    'grant_type': 'authorization_code',
                    'client_id': client_id,
                    'code': code,
                    'redirect_uri': redirect_uri,
                    'code_verifier': code_verifier
                }, timeout=10)
                
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    access_token = token_data.get('access_token', '')
                    refresh_token = token_data.get('refresh_token', '')
                    id_token = token_data.get('id_token', '')
                    print(f"    Access token: {access_token[:30]}...")
                    print(f"    Refresh token: {refresh_token[:30]}...")
                    
                    account_data['access_token'] = access_token
                    account_data['refresh_token'] = refresh_token
                    account_data['id_token'] = id_token
                    account_data['status'] = 'SUCCESS'
                else:
                    print(f"    Token exchange failed: HTTP {token_resp.status_code}")
                    print(f"    Response: {token_resp.text[:200]}")
                    account_data['status'] = 'TOKEN_FAILED'
                break
        
        browser.close()
    except Exception as e:
        print(f"\n    ERROR: {e}")
        account_data['status'] = 'FAILED'
        account_data['error'] = str(e)
        browser.close()

# Save results
print(f"\n{'='*70}")
print(f"Result: {account_data.get('status', 'UNKNOWN')}")

# Save account data
with open('/home/ubuntu/kiro-gen/captured_tokens.json', 'r') as f:
    existing = json.load(f)
existing.append(account_data)
with open('/home/ubuntu/kiro-gen/captured_tokens.json', 'w') as f:
    json.dump(existing, f, indent=2)
print(f"Saved to captured_tokens.json (total: {len(existing)})")

# Save all requests for analysis
with open('/home/ubuntu/kiro-gen/all_requests_capture.json', 'w') as f:
    json.dump({
        'account': account_data,
        'requests': all_requests,
        'responses': all_responses
    }, f, indent=2, default=str)
print(f"Saved {len(all_requests)} requests and {len(all_responses)} responses to all_requests_capture.json")
