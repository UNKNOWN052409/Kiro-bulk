#!/usr/bin/env python3
"""
Final Production Script v4 - Kiro Account Creation
Strategy:
- Browser (no proxy) for sign-in flow (fast, works fine)
- Intercept ALL profile.aws.amazon.com API calls via page.route()
- Replay them through SOCKS5 US proxy (bypasses TES/ERR-837)
- Fulfill intercepted requests with real proxy responses

This way the SPA gets real responses from AWS through a clean residential IP.
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
import threading, imaplib
from urllib.parse import quote, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==================== CONFIG ====================
REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]
CALLBACK_PORT = 9997

# ProxyRise SOCKS5 proxy (US residential)
API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_SOCKS = f'socks5://res-US:{API_KEY}@gw.proxyrise.com:443'

# Gmail
GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_APP_PASSWORD = 'hlcveobitfwh terw'.replace(' ', '')

# Names
FIRST_NAMES = ["Aditya", "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Karan", "Deepika", "Arjun", 
               "Meera", "Rohan", "Kavya", "Nikhil", "Divya", "Siddharth", "Pooja", "Vishal", "Ritu", "Aman",
               "James", "Sarah", "Michael", "Emma", "David", "Olivia", "Daniel", "Sophia", "Matthew", "Isabella",
               "Christopher", "Mia", "Andrew", "Charlotte", "Joshua", "Amelia", "Ryan", "Harper", "Brandon", "Evelyn"]
LAST_NAMES = ["Sharma", "Patel", "Singh", "Kumar", "Gupta", "Verma", "Mehta", "Agarwal", "Joshi", "Reddy",
              "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Anderson", "Taylor", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Moore", "Clark"]

# ==================== HELPERS ====================

def generate_account():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{prefix}@havenhaus.in"
    chars = string.ascii_letters + string.digits + "!@#$%"
    length = random.randint(12, 16)
    password = ''.join(random.choices(chars, k=length))
    if not any(c.isupper() for c in password):
        password = password[:-1] + random.choice(string.ascii_uppercase)
    if not any(c.islower() for c in password):
        password = password[:-2] + random.choice(string.ascii_lowercase) + password[-1]
    if not any(c.isdigit() for c in password):
        password = password[:-3] + random.choice(string.digits) + password[-2:]
    if not any(not c.isalnum() for c in password):
        password = password[:-1] + random.choice("!@#$%")
    return first, last, email, password

def get_otp_from_gmail(email_addr, timeout=120):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            mail.select('inbox')
            status, messages = mail.search(None, f'(TO "{email_addr}")')
            if status == 'OK' and messages[0]:
                msg_ids = messages[0].split()
                for msg_id in reversed(msg_ids[-5:]):
                    status, msg_data = mail.fetch(msg_id, '(BODY.PEEK[])')
                    if status == 'OK':
                        raw = msg_data[0][1]
                        body = raw.decode('utf-8', errors='ignore')
                        otp_match = re.search(r'\b(\d{6})\b', body)
                        if otp_match:
                            mail.logout()
                            return otp_match.group(1)
            mail.logout()
        except:
            pass
        time.sleep(3)
    return None

# ==================== TOKEN SERVER ====================
tokens_captured = {}

class TokenCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if '/oauth/callback' in self.path:
            parsed = urlparse(self.path)
            params = dict(p.split('=', 1) for p in parsed.query.split('&') if '=' in p)
            code = params.get('code', '')
            if code:
                tokens_captured['code'] = code
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'OK')
                return
        self.send_response(404)
        self.end_headers()
    def log_message(self, format, *args):
        pass

# ==================== MAIN ====================

def create_account():
    first_name, last_name, email_addr, password = generate_account()
    full_name = f"{first_name} {last_name}"
    
    result = {
        'first': first_name, 'last': last_name,
        'email': email_addr, 'password': password,
        'status': 'PENDING', 'error': None,
        'access_token': None, 'refresh_token': None, 'id_token': None,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }
    
    print(f"\n{'='*70}")
    print(f"Creating: {full_name} <{email_addr}> | Pass: {password}")
    print(f"Proxy: SOCKS5 US via ProxyRise")
    print(f"{'='*70}")
    
    try:
        # Register OIDC client
        print("[1] Registering OIDC client...")
        reg_payload = {
            "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
            "clientType": "public",
            "scopes": GRANT_SCOPES,
            "grantTypes": ["authorization_code", "refresh_token"],
            "redirectUris": [f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"],
            "issuerUrl": ISSUER_URL
        }
        reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
        reg_resp.raise_for_status()
        client_id = reg_resp.json()['clientId']
        print(f"    Client ID: {client_id[:16]}...")
        
        # PKCE
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
        scopes_encoded = ' '.join(GRANT_SCOPES)
        state = secrets.token_urlsafe(16)
        redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
        auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                    f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
                    f'&state={state}&code_challenge={code_challenge}'
                    f'&code_challenge_method=S256')
        
        # Browser (NO proxy)
        print("[2] Starting browser (no proxy)...")
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
            )
            page = browser.new_page()
            
            # Navigate to auth URL
            print("[3] Navigating to sign-in...")
            page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            
            # Fill email
            print(f"[4] Entering email: {email_addr}")
            email_input = page.locator('input[type="email"]').first
            email_input.click()
            time.sleep(random.uniform(0.3, 0.8))
            for char in email_addr:
                email_input.type(char, delay=random.uniform(30, 80))
            time.sleep(random.uniform(0.5, 1.5))
            
            # Click Continue
            print("[5] Clicking Continue...")
            page.locator('button:has-text("Continue")').first.click()
            time.sleep(random.uniform(3, 6))
            
            # Click Sign up
            print("[6] Clicking Sign up...")
            for selector in ['button:has-text("Sign up")', 'button:has-text("Create account")', 'button:has-text("Get started")']:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        btn.click()
                        print(f"    Clicked: {selector}")
                        break
                except:
                    pass
            
            time.sleep(random.uniform(2, 4))
            
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
                raise Exception(f"No workflowID. URL: {page.url[:100]}")
            
            # Wait for SPA to load
            print("[7] Waiting for SPA to load...")
            spa_loaded = False
            for i in range(30):
                time.sleep(2)
                try:
                    body_text = page.inner_text('body')
                    if len(body_text) > 100:
                        print(f"    SPA loaded after {i*2}s")
                        spa_loaded = True
                        break
                except:
                    pass
            
            if not spa_loaded:
                raise Exception("SPA did not load")
            
            # Fill name
            print(f"[8] Filling name: {full_name}")
            name_input = page.locator('input[type="text"][placeholder]').first
            name_input.click()
            time.sleep(random.uniform(0.3, 0.8))
            for char in full_name:
                name_input.type(char, delay=random.uniform(50, 150))
                time.sleep(random.uniform(0.01, 0.03))
            time.sleep(random.uniform(0.5, 1.5))
            
            # Intercept ALL profile.aws.amazon.com API calls and replay through proxy
            print("[9] Setting up proxy interception...")
            
            def handle_api_route(route):
                req = route.request
                url = req.url
                method = req.method
                post_data = req.post_data
                req_headers = dict(req.headers)
                
                url_path = url.split('profile.aws.amazon.com')[1]
                print(f"    [INTERCEPT] {method} {url_path[:50]}")
                
                # Build headers for replay
                replay_headers = {
                    'Content-Type': req_headers.get('content-type', 'application/json;charset=UTF-8'),
                    'Referer': req_headers.get('referer', f'https://profile.aws.amazon.com/?workflowID={workflow_id}'),
                    'User-Agent': req_headers.get('user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                }
                
                # Replay through SOCKS5 proxy
                try:
                    if method == 'POST':
                        resp = requests.post(url, data=post_data, headers=replay_headers,
                                           proxies={'https': PROXY_SOCKS}, timeout=60)
                    elif method == 'GET':
                        resp = requests.get(url, headers=replay_headers,
                                          proxies={'https': PROXY_SOCKS}, timeout=60)
                    else:
                        resp = requests.request(method, url, headers=replay_headers,
                                              proxies={'https': PROXY_SOCKS}, timeout=60)
                    
                    status_code = resp.status_code
                    response_body = resp.text
                    response_headers = dict(resp.headers)
                    
                    print(f"    [PROXY] HTTP {status_code} - {response_body[:100]}")
                    
                    # Fulfill with real response
                    route.fulfill(
                        status=status_code,
                        content_type='application/json',
                        headers={k: v for k, v in response_headers.items() if k.lower() in ['content-type', 'access-control-allow-origin', 'set-cookie']},
                        body=response_body
                    )
                except Exception as e:
                    print(f"    [PROXY ERROR] {e}")
                    # Fallback: let it through without proxy
                    route.fallback()
            
            # Route ALL profile.aws.amazon.com API requests through proxy
            page.route('**/profile.aws.amazon.com/api/**', handle_api_route)
            
            # Click Continue (triggers /api/send-otp which goes through proxy)
            print("[10] Clicking Continue (name submit)...")
            page.locator('button:has-text("Continue")').first.click()
            time.sleep(random.uniform(3, 6))
            
            # Check result
            body_text = page.inner_text('body')
            print(f"    Body: {body_text[:200]}")
            
            if 'ERR-837' in body_text or 'blocked' in body_text.lower():
                raise Exception(f"ERR-837 still occurring: {body_text[:100]}")
            
            # Check if OTP page
            if 'verification' in body_text.lower() or 'verification code' in body_text.lower() or 'Verify your email' in body_text:
                print("[11] OTP page detected!")
                
                # Get OTP from Gmail
                otp = get_otp_from_gmail(email_addr, timeout=120)
                if not otp:
                    raise Exception("No OTP received from Gmail")
                print(f"    OTP: {otp}")
                
                # Fill OTP
                otp_inputs = page.query_selector_all('input[type="text"]')
                otp_input = None
                for inp in otp_inputs:
                    try:
                        if inp.is_visible():
                            ph = inp.get_attribute('placeholder') or ''
                            if 'code' in ph.lower() or len(otp) <= 6:
                                otp_input = inp
                                break
                    except:
                        pass
                
                if otp_input is None and otp_inputs:
                    for inp in otp_inputs:
                        try:
                            if inp.is_visible():
                                otp_input = inp
                                break
                        except:
                            pass
                
                if otp_input:
                    otp_input.click()
                    time.sleep(0.3)
                    for char in otp:
                        otp_input.type(char, delay=random.uniform(50, 100))
                    time.sleep(random.uniform(0.5, 1.5))
                    
                    # Click Continue
                    try:
                        page.locator('button:has-text("Continue"), button:has-text("Verify")').first.click()
                    except:
                        # Try Enter key
                        otp_input.press('Enter')
                    time.sleep(random.uniform(3, 6))
                    print(f"    URL after OTP: {page.url[:80]}")
            
            # Check for password page
            body_text = page.inner_text('body')
            if 'password' in body_text.lower() and 'enter' in body_text.lower():
                print("[12] Password page detected!")
                pwd_inputs = page.query_selector_all('input[type="password"]')
                if len(pwd_inputs) >= 2:
                    pwd_inputs[0].click()
                    time.sleep(0.3)
                    for char in password:
                        pwd_inputs[0].type(char, delay=random.uniform(30, 80))
                    time.sleep(0.3)
                    pwd_inputs[1].click()
                    time.sleep(0.3)
                    for char in password:
                        pwd_inputs[1].type(char, delay=random.uniform(30, 80))
                elif len(pwd_inputs) == 1:
                    pwd_inputs[0].click()
                    time.sleep(0.3)
                    for char in password:
                        pwd_inputs[0].type(char, delay=random.uniform(30, 80))
                time.sleep(random.uniform(0.5, 1.5))
                
                page.locator('button:has-text("Continue"), button:has-text("Create account")').first.click()
                time.sleep(random.uniform(3, 6))
                print(f"    URL after password: {page.url[:80]}")
            
            # Check for Allow page
            body_text = page.inner_text('body')
            if 'Allow' in body_text and ('access' in body_text.lower() or 'scope' in body_text.lower()):
                print("[13] Allow page detected!")
                time.sleep(random.uniform(1, 3))
                try:
                    page.locator('button:has-text("Allow")').first.click()
                    print("    Allow clicked")
                    time.sleep(random.uniform(2, 4))
                except:
                    try:
                        page.locator('button:has-text("Confirm and continue")').first.click()
                        time.sleep(random.uniform(2, 4))
                        page.locator('button:has-text("Allow")').first.click()
                        print("    Two-step Allow clicked")
                        time.sleep(random.uniform(2, 4))
                    except Exception as e:
                        print(f"    Error on Allow: {e}")
            
            # Wait for token
            print("[14] Waiting for token...")
            token_received = False
            for i in range(30):
                time.sleep(1)
                if 'code' in tokens_captured:
                    code = tokens_captured['code']
                    print(f"    Got auth code!")
                    
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
                        result['access_token'] = token_data.get('access_token', '')
                        result['refresh_token'] = token_data.get('refresh_token', '')
                        result['id_token'] = token_data.get('id_token', '')
                        result['status'] = 'SUCCESS'
                        print(f"    TOKEN CAPTURED! Status: SUCCESS")
                    else:
                        result['status'] = 'TOKEN_FAILED'
                        result['error'] = f"Token exchange failed: HTTP {token_resp.status_code}"
                        print(f"    Token exchange failed: {token_resp.text[:100]}")
                    token_received = True
                    break
            
            if not token_received:
                result['status'] = 'TIMEOUT'
                result['error'] = 'No token captured'
            
            browser.close()
    
    except Exception as e:
        result['status'] = 'FAILED'
        result['error'] = str(e)
        print(f"\n    FAILED: {e}")
    
    return result

if __name__ == '__main__':
    print("\n" + "="*70)
    print("Kiro Account Creator v4 - Selective Proxy via Route Interception")
    print("="*70)
    
    # Start token callback server
    token_server = HTTPServer(('127.0.0.1', CALLBACK_PORT), TokenCallbackHandler)
    token_thread = threading.Thread(target=token_server.serve_forever, daemon=True)
    token_thread.start()
    print(f"Token callback server on port {CALLBACK_PORT}")
    
    # Create account
    result = create_account()
    
    print(f"\n{'='*70}")
    print(f"Result: {result['status']}")
    if result.get('error'):
        print(f"Error: {result['error']}")
    print(f"{'='*70}")
    
    # Save
    tokens_file = '/home/ubuntu/kiro-gen/captured_tokens.json'
    try:
        with open(tokens_file, 'r') as f:
            existing = json.load(f)
    except:
        existing = []
    existing.append(result)
    with open(tokens_file, 'w') as f:
        json.dump(existing, f, indent=2)
    
    success = sum(1 for r in existing if r.get('status') == 'SUCCESS')
    print(f"\nTotal: {len(existing)}, Success: {success}")
