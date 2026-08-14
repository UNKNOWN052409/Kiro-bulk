"""
Batch create Kiro accounts and capture OIDC refresh tokens.
Uses the Authorization Code Flow with PKCE.
KEY FIX: Wait for readyState === 'complete' (takes 50+ seconds) before checking elements.
"""
import sys, os, time, string, random, uuid, json, hashlib, base64, secrets, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from playwright.sync_api import sync_playwright
import csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'

GRANT_SCOPES = [
    "codewhisperer:completions",
    "codewhisperer:analysis",
    "codewhisperer:conversations",
    "codewhisperer:transformations",
    "codewhisperer:taskassist",
]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", 
               "Krishna", "Ishaan", "Shaurya", "Atharv", "Advik", "Kabir", "Rudra",
               "Liam", "Noah", "Ethan", "Lucas", "Mason", "Logan", "Alexander", "James",
               "Benjamin", "William", "Henry", "Theodore", "Jack", "Leo", "Jackson"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Singh", "Patel", "Kumar", "Reddy", "Nair", 
              "Iyer", "Chopra", "Malhotra", "Agarwal", "Joshi", "Mehta", "Rao",
               "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
               "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez"]

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

def generate_password():
    chars = (random.choices(string.ascii_uppercase, k=4) + 
             random.choices(string.ascii_lowercase, k=4) + 
             random.choices(string.digits, k=4) + 
             ['!', '@', '#', '$'])
    random.shuffle(chars)
    return ''.join(chars)

def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def wait_for_render(page, max_wait=90):
    """Wait for the SPA to fully render (readyState === 'complete')."""
    for i in range(max_wait // 2):
        time.sleep(2)
        try:
            ready = page.evaluate("document.readyState")
            if ready == 'complete':
                body = page.evaluate("document.body ? document.body.innerText : ''")
                if len(body) > 50:
                    return True
        except Exception:
            pass
    return False

def dismiss_cookies(page):
    """Dismiss cookie dialog."""
    try:
        for btn_text in ["Decline", "Dismiss"]:
            btns = page.get_by_role("button", name=btn_text, exact=True).all()
            for btn in btns:
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    time.sleep(1)
    except Exception:
        pass
    time.sleep(3)

def logout_aws(page):
    """Log out of AWS session."""
    try:
        page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=15000)
        wait_for_render(page)
        dismiss_cookies(page)
        time.sleep(3)
        try:
            el = page.locator('text=Sign out').first
            if el.is_visible(timeout=3000):
                el.click(timeout=3000)
                time.sleep(5)
        except Exception:
            pass
        return True
    except Exception:
        return False

def capture_token_for_account(email, name, password, callback_port_start=8960):
    authorization_code = None
    callback_event = threading.Event()
    
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal authorization_code
            if '?' in self.path:
                params = dict(p.split('=', 1) for p in self.path.split('?')[1].split('&') if '=' in p)
                if 'code' in params:
                    authorization_code = params['code']
                    callback_event.set()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>OK</h1></body></html>')
        def log_message(self, *a):
            pass
    
    callback_port = callback_port_start
    server = None
    while callback_port < callback_port_start + 100:
        try:
            server = HTTPServer(('127.0.0.1', callback_port), Handler)
            break
        except OSError:
            callback_port += 1
    
    if server is None:
        return None, "No available port"
    
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    redirect_uri = f'http://127.0.0.1:{callback_port}/oauth/callback'
    
    # Register client
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
        return None, f"Register failed: {reg_resp.text[:200]}"
    
    reg_data = reg_resp.json()
    client_id = reg_data['clientId']
    client_secret = reg_data['clientSecret']
    
    # Build auth URL
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
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        # Navigate to auth URL
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        
        # CRITICAL: Wait for full SPA render (takes 50+ seconds)
        wait_for_render(page)
        dismiss_cookies(page)
        wait_for_render(page)  # Re-wait after dismissing cookies
        
        # Check if on Allow page (browser already logged in)
        allow_visible = False
        for btn_text in ["Allow access", "Allow"]:
            try:
                el = page.get_by_role("button", name=btn_text).first
                if el.is_visible(timeout=3000):
                    allow_visible = True
                    break
            except Exception:
                pass
        
        if not allow_visible:
            # Need to login
            # Find email input
            try:
                email_inp = page.locator('input[type="email"]').first
                if email_inp.is_visible(timeout=3000):
                    email_inp.fill(email)
                    page.get_by_role("button", name="Continue").first.click(timeout=5000)
                    time.sleep(5)
                    wait_for_render(page)
                    dismiss_cookies(page)
                    wait_for_render(page)
            except Exception as e:
                pass
            
            # Name step
            try:
                name_inp = page.locator('input[type="text"]').first
                if name_inp.is_visible(timeout=3000):
                    # Make sure it's not the email input again
                    ph = name_inp.get_attribute('placeholder')
                    if ph and 'example' not in ph.lower():
                        name_inp.fill(name)
                        page.get_by_role("button", name="Continue").first.click(timeout=5000)
                        time.sleep(5)
                        wait_for_render(page)
                        dismiss_cookies(page)
                        wait_for_render(page)
            except Exception:
                pass
            
            # OTP step
            try:
                body = page.evaluate("document.body.innerText")
                if 'one-time' in body.lower() or 'verification' in body.lower() or 'code' in body.lower():
                    otp = extract_otp_gmail_v3(email)
                    if otp:
                        otp_inp = page.locator('input[type="text"]').first
                        otp_inp.fill(otp)
                        otp_inp.press('Enter')
                        time.sleep(5)
                        wait_for_render(page)
                        dismiss_cookies(page)
                        wait_for_render(page)
            except Exception:
                pass
            
            # Password step
            try:
                pw_inputs = page.locator('input[type="password"]').all()
                if pw_inputs:
                    pw_inputs[0].fill(password)
                    if len(pw_inputs) > 1:
                        pw_inputs[1].fill(password)
                    page.get_by_role("button", name="Continue").first.click(timeout=5000)
                    time.sleep(5)
                    wait_for_render(page)
                    dismiss_cookies(page)
                    wait_for_render(page)
            except Exception:
                pass
            
            # Confirm code page
            try:
                body = page.evaluate("document.body.innerText")
                if 'confirm' in body.lower() and 'code' in body.lower():
                    page.get_by_role("button", name="Continue").first.click(timeout=5000)
                    time.sleep(5)
                    wait_for_render(page)
                    dismiss_cookies(page)
                    wait_for_render(page)
            except Exception:
                pass
        
        # Allow step
        allow_clicked = False
        for btn_text in ["Allow access", "Allow"]:
            try:
                el = page.get_by_role("button", name=btn_text).first
                if el.is_visible(timeout=5000):
                    el.click(timeout=5000)
                    allow_clicked = True
                    break
            except Exception:
                pass
        
        if not allow_clicked:
            try:
                el = page.get_by_role("button", name="Confirm and continue").first
                if el.is_visible(timeout=5000):
                    el.click(timeout=5000)
                    time.sleep(5)
                    wait_for_render(page)
                    dismiss_cookies(page)
                    wait_for_render(page)
                    el = page.get_by_role("button", name="Allow").first
                    if el.is_visible(timeout=5000):
                        el.click(timeout=5000)
                        allow_clicked = True
            except Exception:
                pass
        
        if not allow_clicked:
            server.shutdown()
            try:
                btns = page.locator('button').all()
                btn_texts = [b.inner_text() for b in btns if b.is_visible()]
            except:
                btn_texts = []
            return None, f"No Allow button. Buttons: {' | '.join(btn_texts)[:100]}"
        
        time.sleep(3)
        
        # Log out after capturing token
        logout_aws(page)
        time.sleep(3)
        
        page.close()
        context.close()
    
    # Wait for callback
    if not callback_event.wait(timeout=120):
        server.shutdown()
        return None, "Timeout waiting for auth code"
    
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
        return None, f"Token exchange failed: {token_resp.text[:200]}"
    
    token_data = token_resp.json()
    if not token_data.get('refreshToken'):
        server.shutdown()
        return None, "No refreshToken"
    
    full_data = {
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
    return full_data, None

def main(num_accounts=10):
    results = []
    print(f"[*] Creating {num_accounts} accounts...")
    
    for i in range(num_accounts):
        email = generate_email()
        name = generate_name()
        password = generate_password()
        
        print(f"\n[{i+1}/{num_accounts}] Creating account: {email}")
        print(f"  Name: {name}")
        
        token_data, error = capture_token_for_account(email, name, password)
        
        if error:
            print(f"  [!] Error: {error}")
            results.append({'email': email, 'name': name, 'password': password, 'error': error})
        else:
            print(f"  [+] Token captured! RT: {token_data['refreshToken'][:30]}...")
            results.append(token_data)
        
        # Save after each account
        with open('/home/ubuntu/kiro-gen/captured_tokens.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        time.sleep(1)
    
    # Save CSV
    csv_file = '/home/ubuntu/kiro-gen/captured_tokens.csv'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Email', 'Name', 'Password', 'RefreshToken', 'AccessToken', 'ExpiresIn', 'Timestamp', 'Error'])
        for r in results:
            writer.writerow([
                r.get('email', ''),
                r.get('name', ''),
                r.get('password', ''),
                r.get('refreshToken', ''),
                r.get('accessToken', ''),
                r.get('expiresIn', ''),
                r.get('timestamp', ''),
                r.get('error', '')
            ])
    
    success = sum(1 for r in results if 'refreshToken' in r)
    failed = sum(1 for r in results if 'error' in r)
    print(f"\n[+] Summary: {success} success, {failed} failed")

if __name__ == '__main__':
    num = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    main(num)
