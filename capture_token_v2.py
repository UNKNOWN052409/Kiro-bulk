"""
Kiro Token Capture v2 - Authorization Code Flow with PKCE
Uses the OIDC authorize endpoint directly (not the SSO portal device flow).
This avoids the "already redeemed" issue because the SPA doesn't call associate_token.
"""
import sys, os, time, string, random, uuid, json, hashlib, base64, secrets, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'

# Kiro scopes (same as Kiro Desktop)
GRANT_SCOPES = [
    "codewhisperer:completions",
    "codewhisperer:analysis",
    "codewhisperer:conversations",
    "codewhisperer:transformations",
    "codewhisperer:taskassist",
]

def dismiss_cookies_sync(page):
    """Dismiss any cookie dialogs."""
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

def generate_password():
    """Generate a strong password."""
    chars = (random.choices(string.ascii_uppercase, k=4) + 
             random.choices(string.ascii_lowercase, k=4) + 
             random.choices(string.digits, k=4) + 
             ['!', '@', '#', '$'])
    random.shuffle(chars)
    return ''.join(chars)

def generate_email():
    """Generate a random email at havenhaus.in."""
    prefix = f"kiro{random.randint(1000, 9999)}{random.choice(string.ascii_lowercase)}{random.randint(10, 99)}"
    return f"{prefix}@havenhaus.in"

def run_auth_flow(email=None, name=None, password=None, callback_port=8902, use_existing_session=False):
    """
    Run the full auth flow:
    1. Register OIDC client
    2. Start local callback server
    3. Navigate to OIDC authorize URL
    4. Login (email, name, OTP, password) if needed
    5. Click Allow
    6. Capture authorization code from callback
    7. Exchange code for tokens
    """
    global authorization_code, callback_event
    
    authorization_code = None
    callback_event = threading.Event()
    
    if email is None:
        email = generate_email()
    if name is None:
        # Generate a human-like name
        first_names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan"]
        last_names = ["Sharma", "Verma", "Gupta", "Singh", "Patel", "Kumar", "Reddy", "Nair", "Iyer", "Chopra"]
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
    if password is None:
        password = generate_password()
    
    # PKCE setup
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    
    # Start callback server
    callback_port = callback_port
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            global authorization_code
            if '?' in self.path or self.path == '/':
                params = dict(p.split('=', 1) for p in self.path.split('?')[1].split('&') if '=' in p) if '?' in self.path else {}
                if 'code' in params:
                    authorization_code = params['code']
                    callback_event.set()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authorization successful!</h1></body></html>')
        
        def log_message(self, format, *args):
            pass
    
    server = HTTPServer(('127.0.0.1', callback_port), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    redirect_uri = f'http://127.0.0.1:{callback_port}/oauth/callback'
    
    # Register OIDC client
    reg_payload = {
        "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
        "clientType": "public",
        "scopes": GRANT_SCOPES,
        "grantTypes": ["authorization_code", "refresh_token"],
        "redirectUris": [redirect_uri],
        "issuerUrl": ISSUER_URL
    }
    
    reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
    if reg_resp.status_code != 200:
        server.shutdown()
        raise Exception(f"Client registration failed: {reg_resp.text[:300]}")
    
    reg_data = reg_resp.json()
    client_id = reg_data['clientId']
    client_secret = reg_data['clientSecret']
    
    # Build authorize URL
    state = secrets.token_urlsafe(16)
    scopes_encoded = ' '.join(GRANT_SCOPES)
    auth_url = (
        f'{OIDC_BASE}/authorize'
        f'?response_type=code'
        f'&client_id={client_id}'
        f'&redirect_uri={redirect_uri}'
        f'&scopes={scopes_encoded}'
        f'&state={state}'
        f'&code_challenge={code_challenge}'
        f'&code_challenge_method=S256'
    )
    
    print(f"[+] Email: {email}")
    print(f"[+] Name: {name}")
    print(f"[+] Auth URL: {auth_url[:100]}...")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(8)
        dismiss_cookies_sync(page)
        
        body = page.evaluate("document.body ? document.body.innerText : ''")
        
        # Check if we're already on the Allow page (existing session)
        buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        
        if 'Allow access' in body or 'Allow' in buttons:
            print("[+] Already on Allow page (existing session)")
        else:
            # Need to login
            # Email
            if 'email' in body.lower() or 'sign in' in body.lower() or 'builder id' in body.lower():
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
        print(f"[+] Buttons: {buttons[:100]}")
        
        if 'Confirm and continue' in buttons:
            page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
            time.sleep(8)
            dismiss_cookies_sync(page)
            buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
            if 'Allow access' in buttons or 'Allow' in buttons:
                page.locator('button:has-text("Allow access")').first.or_(page.locator('button:has-text("Allow")').first).click(timeout=5000)
                print("[+] Allow clicked!")
        elif 'Allow access' in buttons:
            page.locator('button:has-text("Allow access")').first.click(timeout=5000)
            print("[+] Allow clicked!")
        elif 'Allow' in buttons:
            page.locator('button:has-text("Allow")').first.click(timeout=5000)
            print("[+] Allow clicked!")
        else:
            print(f"[!] No Allow button found. Buttons: {buttons}")
        
        time.sleep(3)
        print(f"[+] Final URL: {page.url[:100]}...")
        page.close()
        context.close()
    
    # Wait for callback
    if not callback_event.wait(timeout=120):
        server.shutdown()
        raise Exception("Timeout waiting for authorization code")
    
    # Exchange code for tokens
    token_payload = {
        "clientId": client_id,
        "clientSecret": client_secret,
        "grantType": "authorization_code",
        "code": authorization_code,
        "codeVerifier": code_verifier,
        "redirectUri": redirect_uri
    }
    
    token_resp = requests.post(f'{OIDC_BASE}/token', json=token_payload, timeout=10)
    if token_resp.status_code != 200:
        server.shutdown()
        raise Exception(f"Token exchange failed: {token_resp.text[:300]}")
    
    token_data = token_resp.json()
    refresh_token = token_data.get('refreshToken')
    
    if not refresh_token:
        server.shutdown()
        raise Exception(f"No refreshToken in response: {list(token_data.keys())}")
    
    # Full token data
    full_token_data = {
        **token_data,
        'clientId': client_id,
        'clientSecret': client_secret,
        'codeVerifier': code_verifier,
        'redirectUri': redirect_uri,
        'region': REGION,
        'startUrl': ISSUER_URL,
        'email': email,
        'name': name,
        'password': password,
        'timestamp': time.time()
    }
    
    server.shutdown()
    return full_token_data

if __name__ == '__main__':
    email = sys.argv[1] if len(sys.argv) > 1 else None
    name = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        token_data = run_auth_flow(email=email, name=name)
        print(f"\n[+] *** TOKEN CAPTURED! ***")
        print(f"[+] Email: {token_data['email']}")
        print(f"[+] Refresh Token: {token_data['refreshToken'][:50]}...")
        print(f"[+] Expires In: {token_data.get('expiresIn')}")
        
        # Save to file
        output_file = '/tmp/kiro_token_final.json'
        with open(output_file, 'w') as f:
            json.dump(token_data, f, indent=2)
        print(f"[+] Token saved to {output_file}")
    except Exception as e:
        print(f"[!] Error: {e}")
        sys.exit(1)
