"""
Final production script for Kiro account creation + token capture.
Uses OIDC Authorization Code Flow with PKCE.
Full signup flow: Email -> Name -> Password -> OTP -> Allow -> Token capture.
"""
import sys, time, uuid, requests, secrets, hashlib, base64, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

sys.path.insert(0, '/home/ubuntu/kiro-gen')
from extract_otp_v3 import extract_otp_gmail_v3

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", 
               "Krishna", "Ishaan", "Shaurya", "Atharv", "Advik", "Kabir", "Rudra",
               "Liam", "Noah", "Ethan", "Lucas", "Mason", "Logan", "Alexander", "James",
               "Benjamin", "William", "Henry", "Theodore", "Jack", "Leo", "Jackson"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Singh", "Patel", "Kumar", "Reddy", "Nair", 
              "Iyer", "Chopra", "Malhotra", "Agarwal", "Joshi", "Mehta", "Rao",
               "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
               "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez"]

import string, random

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

def generate_password():
    base = "TestPass" + str(random.randint(1000, 9999))
    special = random.choice("!@#$%")
    return base + special

def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def wait_for_render(page, max_wait=120):
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

def get_visible_inputs(page, input_type=None):
    try:
        all_inputs = page.locator('input').all()
        visible = [inp for inp in all_inputs if inp.is_visible()]
        if input_type:
            visible = [inp for inp in visible if inp.get_attribute('type') == input_type]
        return visible
    except:
        return []

def get_page_body(page):
    try:
        return page.evaluate("document.body ? document.body.innerText : ''")
    except:
        return ""

def wait_and_dismiss(page, extra_wait=10):
    time.sleep(extra_wait)
    wait_for_render(page)
    dismiss_cookies(page)
    wait_for_render(page)

def create_account_and_capture(email, name, password, port_start=8970):
    auth_code_container = {'code': None}
    callback_event = threading.Event()
    
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if '?' in self.path:
                params = dict(p.split('=', 1) for p in self.path.split('?')[1].split('&') if '=' in p)
                if 'code' in params:
                    auth_code_container['code'] = params['code']
                    callback_event.set()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>OK</h1></body></html>')
        def log_message(self, *a):
            pass
    
    callback_port = port_start
    server = None
    while callback_port < port_start + 100:
        try:
            server = HTTPServer(('127.0.0.1', callback_port), Handler)
            break
        except OSError:
            callback_port += 1
    
    if server is None:
        return None, "No available port"
    
    threading.Thread(target=server.serve_forever, daemon=True).start()
    redirect_uri = f'http://127.0.0.1:{callback_port}/oauth/callback'
    
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
    
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    scopes_encoded = ' '.join(GRANT_SCOPES)
    state = secrets.token_urlsafe(16)
    auth_url = f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scopes={scopes_encoded}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256'
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        
        # Close all existing pages except one
        for pg in context.pages[1:]:
            try: pg.close()
            except: pass
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Navigate to auth URL
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        
        # Wait for full render
        wait_for_render(page)
        dismiss_cookies(page)
        wait_for_render(page)
        
        body = get_page_body(page)
        body_lower = body.lower()
        allow_clicked = False
        
        # Check if already on Allow page
        if 'allow access' in body_lower or ('allow' in body_lower and 'cookie' not in body_lower[:100]):
            for btn_text in ["Allow access", "Allow"]:
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.is_visible(timeout=3000):
                        btn.click(timeout=5000)
                        allow_clicked = True
                        print(f"    Already on Allow page, clicked Allow")
                        break
                except:
                    pass
        
        if not allow_clicked:
            # STEP 1: Email entry page
            email_inputs = get_visible_inputs(page, 'email')
            if email_inputs:
                print(f"    Email page detected. Filling: {email}")
                email_inputs[0].fill(email)
                time.sleep(1)
                try:
                    page.get_by_role("button", name="Continue").first.click(timeout=5000)
                    print(f"    Email submitted")
                except Exception as e:
                    print(f"    Error clicking Continue: {e}")
                
                wait_and_dismiss(page, 15)
                body = get_page_body(page)
                body_lower = body.lower()
                print(f"    After email: {body[:80]}")
            else:
                pw_inputs = get_visible_inputs(page, 'password')
                if pw_inputs:
                    print(f"    Password page (email pre-filled). Filling password...")
                    pw_inputs[0].fill(password)
                    if len(pw_inputs) > 1:
                        pw_inputs[1].fill(password)
                    time.sleep(1)
                    try:
                        page.get_by_role("button", name="Continue").first.click(timeout=5000)
                        print(f"    Password submitted")
                    except:
                        pass
                    wait_and_dismiss(page, 15)
                    body = get_page_body(page)
                    body_lower = body.lower()
        
        # STEP 2: Name entry page (new accounts go here)
        if not allow_clicked and 'enter your name' in body_lower:
            text_inputs = get_visible_inputs(page, 'text')
            if text_inputs:
                print(f"    Name page detected. Filling: {name}")
                text_inputs[0].fill(name)
                time.sleep(1)
                try:
                    page.get_by_role("button", name="Continue").first.click(timeout=5000)
                    print(f"    Name submitted")
                except:
                    pass
                
                wait_and_dismiss(page, 15)
                body = get_page_body(page)
                body_lower = body.lower()
                print(f"    After name: {body[:80]}")
        
        # STEP 3: Password creation page
        if not allow_clicked:
            pw_inputs = get_visible_inputs(page, 'password')
            if pw_inputs and 'allow' not in body_lower:
                print(f"    Password page detected. Filling password...")
                pw_inputs[0].fill(password)
                if len(pw_inputs) > 1:
                    pw_inputs[1].fill(password)
                time.sleep(1)
                try:
                    page.get_by_role("button", name="Continue").first.click(timeout=5000)
                    print(f"    Password submitted")
                except:
                    pass
                
                wait_and_dismiss(page, 15)
                body = get_page_body(page)
                body_lower = body.lower()
                print(f"    After password: {body[:80]}")
        
        # STEP 4: OTP verification page
        if not allow_clicked and ('verification' in body_lower or 'one-time' in body_lower or 'check your email' in body_lower or 'security code' in body_lower):
            print(f"    OTP page detected. Extracting OTP...")
            otp = extract_otp_gmail_v3(email)
            if otp:
                print(f"    OTP: {otp}")
                text_inputs = get_visible_inputs(page, 'text')
                if text_inputs:
                    text_inputs[-1].fill(otp)
                    time.sleep(2)
                    for btn_text in ["Verify", "Continue", "Submit"]:
                        try:
                            btn = page.get_by_role("button", name=btn_text).first
                            if btn.is_visible(timeout=3000):
                                btn.click(timeout=5000)
                                print(f"    Clicked: {btn_text}")
                                break
                        except:
                            pass
                else:
                    all_inputs = get_visible_inputs(page)
                    for inp in all_inputs:
                        inp_type = inp.get_attribute('type') or 'text'
                        if inp_type in ('text', 'number', 'tel'):
                            inp.fill(otp)
                            time.sleep(2)
                            try:
                                page.get_by_role("button", name="Verify").first.click(timeout=5000)
                                print(f"    OTP filled and Verify clicked")
                                break
                            except:
                                pass
                
                wait_and_dismiss(page, 15)
                body = get_page_body(page)
                body_lower = body.lower()
                print(f"    After OTP: {body[:80]}")
            else:
                print(f"    [!] OTP extraction failed")
        
        # STEP 5: Confirm page
        if not allow_clicked and 'confirm' in body_lower and 'allow' not in body_lower:
            print(f"    Confirm page detected.")
            for btn_text in ["Confirm and continue", "Continue", "Confirm"]:
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.is_visible(timeout=3000):
                        btn.click(timeout=5000)
                        print(f"    Clicked: {btn_text}")
                        time.sleep(5)
                        wait_and_dismiss(page, 5)
                        body = get_page_body(page)
                        body_lower = body.lower()
                        break
                except:
                    pass
        
        # STEP 6: Allow page
        if not allow_clicked:
            # One more render wait in case we're on Allow page
            time.sleep(10)
            wait_for_render(page)
            body = get_page_body(page)
            body_lower = body.lower()
            
            for btn_text in ["Allow access", "Allow"]:
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.is_visible(timeout=5000):
                        btn.click(timeout=5000)
                        allow_clicked = True
                        print(f"    Clicked: {btn_text}")
                        break
                except:
                    pass
        
        if not allow_clicked:
            body = get_page_body(page)
            return None, f"No Allow. Body: {body[:200]}"
        
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
        "code": auth_code_container['code'],
        "codeVerifier": code_verifier,
        "redirectUri": redirect_uri
    }
    
    token_resp = requests.post(f'{OIDC_BASE}/token', json=token_payload, timeout=10)
    if token_resp.status_code != 200:
        server.shutdown()
        return None, f"Token failed: {token_resp.text[:200]}"
    
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
        'authMethod': 'builder-id',
        'email': email,
        'name': name,
        'password': password,
        'timestamp': time.time()
    }
    
    server.shutdown()
    return full_data, None

def main(num_accounts=10):
    import json, csv
    
    results = []
    print(f"[*] Creating {num_accounts} accounts...")
    
    for i in range(num_accounts):
        email = generate_email()
        name = generate_name()
        password = generate_password()
        
        print(f"\n[{i+1}/{num_accounts}] {email} ({name})")
        print(f"  Password: {password}")
        
        token_data, error = create_account_and_capture(email, name, password)
        
        if error:
            print(f"  [!] Error: {error[:150]}")
            results.append({'email': email, 'name': name, 'password': password, 'error': error})
        else:
            print(f"  [+] Token captured! RT: {token_data['refreshToken'][:30]}...")
            results.append(token_data)
        
        # Save after each account
        with open('/home/ubuntu/kiro-gen/captured_tokens.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        time.sleep(2)
    
    # Save CSV
    csv_file = '/home/ubuntu/kiro-gen/captured_tokens.csv'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Email', 'Name', 'Password', 'RefreshToken', 'AccessToken', 'ExpiresIn', 'Error'])
        for r in results:
            writer.writerow([
                r.get('email', ''),
                r.get('name', ''),
                r.get('password', ''),
                r.get('refreshToken', ''),
                r.get('accessToken', ''),
                r.get('expiresIn', ''),
                r.get('error', '')
            ])
    
    success = sum(1 for r in results if 'refreshToken' in r)
    failed = sum(1 for r in results if 'error' in r)
    print(f"\n[+] Summary: {success} success, {failed} failed")

if __name__ == '__main__':
    num = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    main(num)
