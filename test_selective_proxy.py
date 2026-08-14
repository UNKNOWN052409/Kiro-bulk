#!/usr/bin/env python3
"""
Selective Proxy Test:
- Use proxy ONLY for profile.aws.amazon.com API requests (intercepted via page.route())
- Direct connection for everything else (browser, SPA loading)
This bypasses the SPA rendering issue since we only proxy the API calls, not the page resources.
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
import threading
from urllib.parse import quote, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

# ProxyRise proxy
PROXY_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_HTTP = f'http://res-any:{PROXY_API_KEY}@gw.proxyrise.com:443'
PROXY_HTTP_US = f'http://res-US:{PROXY_API_KEY}@gw.proxyrise.com:443'
PROXY_SOCKS = f'socks5://res-any:{PROXY_API_KEY}@gw.proxyrise.com:443'

FIRST_NAMES = ["James", "Sarah", "Michael", "Emma", "David", "Olivia", "Daniel", "Sophia"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]

def generate_account():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{prefix}@havenhaus.in"
    return first, last, email

first_name, last_name, email_addr = generate_account()
full_name = f"{first_name} {last_name}"
print(f"Account: {full_name} <{email_addr}>")

# Test proxy connectivity
print("\n[Proxy Test] Testing ProxyRise...")
working_proxy = None
for name, url in [("HTTP any", PROXY_HTTP), ("HTTP US", PROXY_HTTP_US), ("SOCKS5", PROXY_SOCKS)]:
    try:
        resp = requests.get('https://api.ipquery.io/?format=json', proxies={'https': url}, timeout=15)
        ip_data = resp.json()
        print(f"  {name}: IP={ip_data.get('ip','?')}, {ip_data.get('city','?')}, {ip_data.get('country','?')}, ISP={ip_data.get('isp','?')}")
        if not working_proxy:
            working_proxy = url
            print(f"    -> Using this proxy")
    except Exception as e:
        print(f"  {name}: FAILED ({e})")

if not working_proxy:
    print("  No proxy working! Exiting.")
    exit(1)

print(f"\n  Selected proxy: {working_proxy}")

# Register OIDC client (no proxy)
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
print(f"    Client ID: {client_id[:16]}...")

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

# Token callback server
tokens_captured = {}

class CallbackHandler(BaseHTTPRequestHandler):
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

token_server = HTTPServer(('127.0.0.1', 9997), CallbackHandler)
token_thread = threading.Thread(target=token_server.serve_forever, daemon=True)
token_thread.start()
print(f"Token server on :9997")

# Main flow
print(f"\n[1] Starting browser (NO proxy - direct IP for everything)...")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    try:
        # Navigate to auth URL
        print("[2] Navigating to sign-in...")
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)
        
        # Fill email
        print(f"[3] Entering email: {email_addr}")
        email_input = page.locator('input[type="email"]').first
        email_input.click()
        time.sleep(0.3)
        for char in email_addr:
            email_input.type(char, delay=random.uniform(30, 80))
        time.sleep(1)
        
        # Click Continue
        print("[4] Clicking Continue...")
        page.locator('button:has-text("Continue")').first.click()
        time.sleep(5)
        
        # Click Sign up
        print("[5] Clicking Sign up...")
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
        print("[6] Waiting for SPA to load...")
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
        print(f"[7] Filling name: {full_name}")
        name_input = page.locator('input[type="text"][placeholder]').first
        name_input.click()
        time.sleep(0.3)
        for char in full_name:
            name_input.type(char, delay=random.uniform(50, 150))
            time.sleep(random.uniform(0.01, 0.03))
        time.sleep(1)
        
        # Intercept the API call that triggers ERR-837 and replay through proxy
        print("[8] Setting up request interception...")
        captured_request = None
        
        def handle_intercepted(route):
            global captured_request
            url_path = route.request.url.split('profile.aws.amazon.com')[1] if 'profile.aws.amazon.com' in route.request.url else ''
            print(f"    [ROUTE] {route.request.method} {url_path}")
            captured_request = {
                'url': route.request.url,
                'method': route.request.method,
                'headers': dict(route.request.headers),
                'post_data': route.request.post_data
            }
            # Fulfill with empty 200 to satisfy the SPA
            route.fulfill(status=200, content_type='application/json', body='{"workflowState":"PLACEHOLDER"}')
            print(f"    [ROUTE] Fulfilled with placeholder - will replay real request via proxy")
        
        page.route('**/profile.aws.amazon.com/api/send-otp', handle_intercepted)
        
        # Click Continue (triggers the API call which we intercept)
        print("[9] Clicking Continue (name submit)...")
        page.locator('button:has-text("Continue")').first.click()
        time.sleep(5)
        
        if captured_request:
            print(f"\n[10] Replaying through proxy: {working_proxy}")
            
            # Build headers for replay
            replay_headers = {
                'Content-Type': 'application/json;charset=UTF-8',
            }
            for h in ['referer', 'user-agent', 'origin', 'accept']:
                if h in captured_request['headers']:
                    replay_headers[h.capitalize() if h != 'user-agent' else 'User-Agent'] = captured_request['headers'][h]
            
            print(f"    URL: {captured_request['url'][:80]}")
            print(f"    Method: {captured_request['method']}")
            print(f"    Headers: {json.dumps(replay_headers)[:200]}")
            if captured_request['post_data']:
                print(f"    Body: {captured_request['post_data'][:200]}")
            
            # Replay through proxy
            try:
                if captured_request['method'] == 'POST':
                    resp = requests.post(captured_request['url'], 
                                        data=captured_request['post_data'],
                                        headers=replay_headers,
                                        proxies={'https': working_proxy},
                                        timeout=120)
                else:
                    resp = requests.get(captured_request['url'],
                                       headers=replay_headers,
                                       proxies={'https': working_proxy},
                                       timeout=30)
                
                print(f"\n    [PROXY RESPONSE] HTTP {resp.status_code}")
                print(f"    [PROXY RESPONSE] Body: {resp.text[:300]}")
                
                if resp.status_code == 200 and 'BLOCKED' not in resp.text:
                    print(f"    SUCCESS! Proxy bypassed the block!")
                elif 'BLOCKED' in resp.text or 'TES' in resp.text:
                    print(f"    Still blocked by TES even with proxy IP")
                else:
                    print(f"    Other response - check status")
            except Exception as e:
                print(f"    Proxy replay failed: {e}")
        else:
            print("    No request was intercepted!")
        
        # Check final page state
        time.sleep(2)
        try:
            body_text = page.inner_text('body')
            print(f"\n    Final page state: {body_text[:200]}")
        except:
            pass
        
        browser.close()
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        browser.close()

print(f"\n{'='*60}")
