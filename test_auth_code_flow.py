"""Authorization Code Flow with PKCE - the Kiro CLI approach."""
import sys, os, time, string, random, uuid, json, hashlib, base64, secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from playwright.sync_api import sync_playwright
import boto3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

# PKCE setup
code_verifier = secrets.token_urlsafe(64)[:128]  # 43-128 chars
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()

# Local callback server
callback_port = 8901
authorization_code = None
callback_event = threading.Event()

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global authorization_code
        # Parse the callback URL
        if '?' in self.path or self.path == '/':
            params = dict(p.split('=') for p in self.path.split('?')[1].split('&'))
            if 'code' in params:
                authorization_code = params['code']
                print(f"[+] Authorization code received: {authorization_code[:20]}...")
                callback_event.set()
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>')
    
    def log_message(self, format, *args):
        pass  # Suppress logging

# Start callback server
server = HTTPServer(('127.0.0.1', callback_port), CallbackHandler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
print(f"[+] Callback server started on port {callback_port}")

# Register OIDC client with redirect URI
client = boto3.client('sso-oidc', region_name='us-east-1')
redirect_uri = f'http://127.0.0.1:{callback_port}'
reg = client.register_client(
    clientName=f'kiro-{uuid.uuid4().hex[:8]}',
    clientType='public',
    redirectUris=[redirect_uri],
    grantTypes=['authorization_code'],
    scopes=['sso:account:access'],
    issuerUrl='https://view.awsapps.com/start'
)
client_id = reg['clientId']
client_secret = reg['clientSecret']
print(f"[+] Client registered: {client_id}")

# Build authorization URL
auth_url = (
    f'https://view.awsapps.com/start/#/oauth2/authorize'
    f'?client_id={client_id}'
    f'&redirect_uri={redirect_uri}'
    f'&response_type=code'
    f'&code_challenge={code_challenge}'
    f'&code_challenge_method=S256'
    f'&state={secrets.token_urlsafe(16)}'
)
print(f"[+] Auth URL: {auth_url[:150]}...")

email = sys.argv[1] if len(sys.argv) > 1 else "testpy039@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)

def dismiss_cookies_sync(page):
    for _ in range(10):
        for btn_text in ["Decline", "Dismiss", "Accept"]:
            try:
                btns = page.locator(f'button:has-text("{btn_text}")').all()
                for btn in btns:
                    if btn.is_visible(timeout=1000):
                        btn.click(timeout=2000)
                        time.sleep(0.5)
            except Exception:
                pass
        time.sleep(1)
        body = page.evaluate("document.body ? document.body.innerText : ''")
        if body and len(body) > 50 and 'cookie' not in body.lower()[:100]:
            break
    time.sleep(2)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Navigate to the authorization URL
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(8)
    dismiss_cookies_sync(page)
    
    # Email
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'email' in body.lower() or 'sign in' in body.lower():
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.wait_for(timeout=10000)
            inp.fill(email)
            inp.press('Enter')
            print("[+] Email submitted")
        except Exception as e:
            print(f"[!] Email: {e}")
        time.sleep(5)
    dismiss_cookies_sync(page)
    
    # Name
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'name' in body.lower():
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.fill(name)
            page.locator('button:has-text("Continue")').first.click(timeout=3000)
            print("[+] Name submitted")
        except Exception as e:
            print(f"[!] Name: {e}")
        time.sleep(5)
    dismiss_cookies_sync(page)
    
    # OTP
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'verify' in body.lower() or 'one-time' in body.lower() or ('code' in body.lower() and 'enter' in body.lower()):
        otp = extract_otp_gmail_v3(email)
        if otp:
            try:
                inp = page.locator('input:visible').first
                inp.fill(otp)
                inp.press('Enter')
                print(f"[+] OTP: {otp}")
            except Exception as e:
                print(f"[!] OTP: {e}")
            time.sleep(5)
    dismiss_cookies_sync(page)
    
    # Password
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'password' in body.lower():
        try:
            inputs = page.locator('input[type="password"]:visible').all()
            if inputs:
                inputs[0].fill(password)
                if len(inputs) > 1:
                    inputs[1].fill(password)
                page.locator('button:has-text("Continue")').first.click(timeout=3000)
                print("[+] Password submitted")
        except Exception as e:
            print(f"[!] Password: {e}")
        time.sleep(5)
    dismiss_cookies_sync(page)
    
    # Allow
    body = page.evaluate("document.body ? document.body.innerText : ''")
    buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
    print(f"[+] Buttons: {buttons}")
    
    if 'Confirm and continue' in buttons:
        page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
        time.sleep(8)
        dismiss_cookies_sync(page)
        body = page.evaluate("document.body ? document.body.innerText : ''")
        buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        if 'Allow' in buttons:
            page.locator('button:has-text("Allow")').first.click(timeout=5000)
            print("[+] Allow clicked!")
    elif 'Allow' in buttons:
        page.locator('button:has-text("Allow")').first.click(timeout=5000)
        print("[+] Allow clicked!")
    
    time.sleep(5)
    print(f"[+] Final URL: {page.url}")
    page.close()
    context.close()

# Wait for the callback
print("\n[*] Waiting for authorization code...")
if callback_event.wait(timeout=60):
    print(f"[+] Authorization code: {authorization_code}")
    
    # Exchange the code for tokens
    try:
        resp = client.create_token(
            clientId=client_id,
            clientSecret=client_secret,
            grantType='authorization_code',
            code=authorization_code,
            codeVerifier=code_verifier,
            redirectUri=redirect_uri
        )
        token = resp.get('refreshToken')
        if token:
            print(f"\n[+] *** TOKEN CAPTURED! ***")
            print(f"[+] Access Token: {resp.get('accessToken', '')[:50]}...")
            print(f"[+] Refresh Token: {token[:50]}...")
            print(f"[+] Expires In: {resp.get('expiresIn')}")
            print(f"[+] Token Type: {resp.get('tokenType')}")
            
            # Save to file
            token_data = {
                'accessToken': resp.get('accessToken'),
                'refreshToken': token,
                'expiresIn': resp.get('expiresIn'),
                'tokenType': resp.get('tokenType'),
                'clientId': client_id,
                'clientSecret': client_secret,
                'codeVerifier': code_verifier,
                'redirectUri': redirect_uri,
                'region': 'us-east-1',
                'startUrl': 'https://view.awsapps.com/start',
                'email': email,
                'password': password,
                'timestamp': time.time()
            }
            with open('/tmp/kiro_token_authcode.txt', 'w') as f:
                json.dump(token_data, f, indent=2)
            print(f"[+] Token saved to /tmp/kiro_token_authcode.txt")
        else:
            print(f"[!] No refreshToken in response: {list(resp.keys())}")
    except Exception as e:
        print(f"[!] Token exchange error: {e}")
else:
    print("[!] Timeout waiting for authorization code")

server.shutdown()
