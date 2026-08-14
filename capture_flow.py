"""
Capture the complete AWS/Kiro flow using browser through local proxy wrapper.
mitmproxy on port 8080 logs all requests to captured_flow.json.
Browser uses proxy wrapper (localhost:8899) for residential IP.
"""

import uuid, secrets, hashlib, base64, random, string, time
import threading, socket, subprocess
from urllib.parse import quote

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]
CALLBACK_PORT = 9997
LOCAL_PROXY_PORT = 8899

PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_SESSION_ID = str(random.randint(10000, 999999999))

# Generate account
first = "Test"
last = "User"
prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
email = f"{prefix}@havenhaus.in"
chars = string.ascii_letters + string.digits + "!@#$%"
password = ''.join(random.choices(chars, k=14))
if not any(c.isupper() for c in password):
    password += "A"
full_name = f"{first} {last}"

print(f"Email: {email}")
print(f"Password: {password}")
print(f"Proxy session: {PROXY_SESSION_ID}")

# Start proxy wrapper
def start_proxy():
    proc = subprocess.Popen(
        ['python3', '/home/ubuntu/kiro-gen/proxy_wrapper.py', PROXY_SESSION_ID],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(10):
        try:
            s = socket.create_connection(('127.0.0.1', LOCAL_PROXY_PORT), timeout=1)
            s.close()
            return proc
        except:
            time.sleep(0.5)
    return proc

# Register OIDC client
import requests
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": [f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']
print(f"Client ID: {client_id}")

code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

# Start proxy
print("\nStarting proxy wrapper...")
proxy_proc = start_proxy()
print("Proxy ready!")

# Token capture
tokens_captured = {}
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

class TokenHandler(BaseHTTPRequestHandler):
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

token_server = HTTPServer(('127.0.0.1', CALLBACK_PORT), TokenHandler)
token_thread = threading.Thread(target=token_server.serve_forever, daemon=True)
token_thread.start()

# Browser flow through local proxy (residential IP)
from playwright.sync_api import sync_playwright

def human_type(page, locator, text, min_delay=50, max_delay=150):
    for char in text:
        locator.type(char, delay=random.uniform(min_delay, max_delay))
        time.sleep(random.uniform(0.02, 0.08))

print("\nStarting browser (through local proxy -> residential IP)...")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled',
              '--disable-infobars', '--disable-extensions', '--window-size=1920,1080']
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
        locale='en-US',
        timezone_id='America/New_York',
        ignore_https_errors=True,
        proxy={'server': f'http://127.0.0.1:{LOCAL_PROXY_PORT}'},
    )
    page = context.new_page()
    
    # Navigate to auth URL
    print(f"  Navigating to authorize...")
    page.goto(auth_url, wait_until='domcontentloaded', timeout=120000)
    
    # Wait for signin page
    print("  Waiting for signin page...")
    for i in range(60):
        time.sleep(2)
        url = page.url
        body = ''
        try:
            body = page.evaluate('document.body.innerText')
        except:
            pass
        
        if 'signin.aws' in url and 'workflowStateHandle' in url:
            has_form = False
            try:
                has_form = page.locator('input[type="email"], input[name="username"]').first.is_visible(timeout=2000)
            except:
                pass
            if has_form:
                print(f"  Signin form visible [{i*2}s]")
                break
        
        if 'profile.aws.amazon.com' in url:
            print(f"  Already on profile [{i*2}s]")
            break
    
    print(f"  URL: {page.url[:100]}")
    
    # Fill email
    if 'signin.aws' in page.url:
        print("  Filling email...")
        email_input = page.locator('input[type="email"], input[name="username"]').first
        if email_input.is_visible():
            human_type(page, email_input, email)
            time.sleep(1)
            # Click Continue
            try:
                btn = page.locator('button:has-text("Continue")').first
                if btn.is_visible():
                    btn.click()
                    print("  Continue clicked")
            except:
                pass
    
    # Wait for profile page
    print("  Waiting for profile.aws.amazon.com...")
    for i in range(90):
        time.sleep(2)
        url = page.url
        body = ''
        try:
            body = page.evaluate('document.body.innerText')
        except:
            pass
        
        if 'profile.aws.amazon.com' in url:
            print(f"  On profile! [{i*2}s]")
            break
        
        if i % 10 == 0:
            print(f"  [{i*2}s] URL: {url[:80]}, body: {body[:50]}")
    
    print(f"  URL: {page.url[:100]}")
    
    # Wait for SPA to load
    for i in range(60):
        time.sleep(2)
        body = ''
        try:
            body = page.evaluate('document.body.innerText')
        except:
            pass
        
        bt = body.lower()
        if 'enter your name' in bt or ('name' in bt and 'email' in bt and len(body) > 20):
            print(f"  Name form loaded [{i*2}s]: {body[:80]}")
            break
        elif 'err-837' in bt:
            print(f"  ERR-837 at [{i*2}s]")
            break
        elif 'timed out' in bt or 'oh no' in bt:
            print(f"  Timeout at [{i*2}s]")
            break
        
        if i % 10 == 0 and i > 0:
            print(f"  [{i*2}s] body: {body[:60]}")
    
    # Fill name
    body = ''
    try:
        body = page.evaluate('document.body.innerText')
    except:
        pass
    
    if 'name' in body.lower() and 'email' in body.lower():
        print("\n  Filling name...")
        try:
            name_input = page.locator('input[type="text"]').first
            if name_input.is_visible():
                name_input.click()
                time.sleep(0.5)
                human_type(page, name_input, full_name)
                time.sleep(1)
                name_input.press('Enter')
                print("  Name submitted via Enter")
        except Exception as e:
            print(f"  Name error: {e}")
    
    # Wait for OTP
    print("\n  Waiting for OTP page...")
    for i in range(60):
        time.sleep(2)
        body = ''
        try:
            body = page.evaluate('document.body.innerText')
        except:
            pass
        
        bt = body.lower()
        if 'verification code' in bt or ('code' in bt and 'enter' in bt):
            print(f"  OTP page at [{i*2}s]: {body[:80]}")
            break
        
        if i % 10 == 0 and i > 0:
            print(f"  [{i*2}s] body: {body[:60]}")
    
    # Check token
    if 'code' in tokens_captured:
        print(f"\n  TOKEN CAPTURED: {tokens_captured['code'][:40]}...")
    
    print(f"\n  Final URL: {page.url[:100]}")
    body = ''
    try:
        body = page.evaluate('document.body.innerText')
    except:
        pass
    print(f"  Final body: {body[:200]}")
    
    browser.close()

proxy_proc.terminate()
print("\nDone!")
