"""Debug the full flow step by step."""
import sys, time, uuid, requests, secrets, hashlib, base64, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

sys.path.insert(0, '/home/ubuntu/kiro-gen')
from extract_otp_v3 import extract_otp_gmail_v3

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

def wait_for_render(page, max_wait=90):
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

# Setup callback server
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

server = HTTPServer(('127.0.0.1', 9990), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

redirect_uri = 'http://127.0.0.1:9990/oauth/callback'

# Register
reg_payload = {
    "clientName": f"kiro-debug-{uuid.uuid4().hex[:6]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": [redirect_uri],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']
client_secret = reg_resp.json()['clientSecret']

code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
auth_url = f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scopes={scopes_encoded}&state=test&code_challenge={code_challenge}&code_challenge_method=S256'

test_email = "debugtest02@havenhaus.in"
test_name = "Debug Test"
test_password = "Test1234!@ab"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    print("[*] Navigating to auth URL...")
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    
    print("[*] Waiting for render...")
    wait_for_render(page)
    print(f"  Rendered. URL: {page.url[:80]}")
    
    dismiss_cookies(page)
    wait_for_render(page)
    
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] Step 1 - Initial page body:")
    print(f"    {body[:300]}")
    
    # Email step
    print("\n[*] Step 2 - Filling email...")
    try:
        email_inp = page.locator('input[type="email"]').first
        email_inp.fill(test_email)
        time.sleep(1)
        page.get_by_role("button", name="Continue").first.click(timeout=5000)
        print(f"  Email filled and submitted")
    except Exception as e:
        print(f"  Error: {e}")
    
    time.sleep(15)
    wait_for_render(page)
    dismiss_cookies(page)
    wait_for_render(page)
    
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] Step 3 - After email submit:")
    print(f"    {body[:300]}")
    
    # Check for name input
    print("\n[*] Step 4 - Looking for name input...")
    try:
        text_inputs = page.locator('input[type="text"]').all()
        visible_inputs = [inp for inp in text_inputs if inp.is_visible()]
        print(f"  Visible text inputs: {len(visible_inputs)}")
        for inp in visible_inputs:
            ph = inp.get_attribute('placeholder')
            print(f"    placeholder: {ph}")
        
        if visible_inputs:
            # Fill first visible text input that's not OTP
            inp = visible_inputs[0]
            ph = inp.get_attribute('placeholder') or ''
            if 'verification' not in ph.lower() and 'otp' not in ph.lower():
                inp.fill(test_name)
                time.sleep(1)
                page.get_by_role("button", name="Continue").first.click(timeout=5000)
                print(f"  Name filled and submitted")
    except Exception as e:
        print(f"  Error: {e}")
    
    time.sleep(15)
    wait_for_render(page)
    dismiss_cookies(page)
    wait_for_render(page)
    
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] Step 5 - After name submit:")
    print(f"    {body[:300]}")
    
    # OTP step
    print("\n[*] Step 6 - Looking for OTP...")
    try:
        # Check all inputs
        all_inputs = page.locator('input').all()
        visible_inputs = [inp for inp in all_inputs if inp.is_visible()]
        print(f"  Visible inputs: {len(visible_inputs)}")
        for inp in visible_inputs:
            t = inp.get_attribute('type')
            ph = inp.get_attribute('placeholder') or ''
            print(f"    type={t}, placeholder={ph}")
        
        # Try to extract OTP
        otp = extract_otp_gmail_v3(test_email)
        print(f"  OTP extracted: {otp}")
        
        if otp and visible_inputs:
            # Find the OTP input
            otp_inp = None
            for inp in visible_inputs:
                t = inp.get_attribute('type') or ''
                ph = inp.get_attribute('placeholder') or ''
                if t == 'text' and len(ph) > 0:
                    otp_inp = inp
                    break
            if otp_inp is None and visible_inputs:
                otp_inp = visible_inputs[-1]
            
            if otp_inp:
                otp_inp.fill(otp)
                time.sleep(2)
                
                # Click Verify or Continue
                clicked = False
                for btn_text in ["Verify", "Continue"]:
                    try:
                        btn = page.get_by_role("button", name=btn_text).first
                        if btn.is_visible(timeout=3000):
                            btn.click(timeout=5000)
                            clicked = True
                            print(f"  Clicked: {btn_text}")
                            break
                    except Exception:
                        pass
                
                if not clicked:
                    otp_inp.press('Enter')
                    print("  Pressed Enter")
    except Exception as e:
        print(f"  Error: {e}")
    
    time.sleep(15)
    wait_for_render(page)
    dismiss_cookies(page)
    wait_for_render(page)
    
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] Step 7 - After OTP submit:")
    print(f"    {body[:300]}")
    
    # Password step
    print("\n[*] Step 8 - Looking for password input...")
    try:
        pw_inputs = page.locator('input[type="password"]').all()
        visible_pw = [inp for inp in pw_inputs if inp.is_visible()]
        print(f"  Visible password inputs: {len(visible_pw)}")
        
        if visible_pw:
            visible_pw[0].fill(test_password)
            if len(visible_pw) > 1:
                visible_pw[1].fill(test_password)
            time.sleep(1)
            
            clicked = False
            for btn_text in ["Continue", "Verify"]:
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.is_visible(timeout=3000):
                        btn.click(timeout=5000)
                        clicked = True
                        print(f"  Clicked: {btn_text}")
                        break
                except Exception:
                    pass
            
            if not clicked:
                visible_pw[0].press('Enter')
                print("  Pressed Enter")
    except Exception as e:
        print(f"  Error: {e}")
    
    time.sleep(15)
    wait_for_render(page)
    dismiss_cookies(page)
    wait_for_render(page)
    
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] Step 9 - After password submit:")
    print(f"    {body[:300]}")
    
    # Confirm code step
    print("\n[*] Step 10 - Looking for confirm code...")
    try:
        confirm_btn = None
        for btn_text in ["Continue", "Confirm and continue"]:
            try:
                btn = page.get_by_role("button", name=btn_text).first
                if btn.is_visible(timeout=3000):
                    confirm_btn = btn
                    print(f"  Found: {btn_text}")
                    break
            except Exception:
                pass
        
        if confirm_btn:
            confirm_btn.click(timeout=5000)
            time.sleep(5)
            wait_for_render(page)
            dismiss_cookies(page)
            wait_for_render(page)
    except Exception:
        pass
    
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] Step 11 - After confirm:")
    print(f"    {body[:300]}")
    
    # Allow step
    print("\n[*] Step 12 - Looking for Allow...")
    allow_clicked = False
    for btn_text in ["Allow access", "Allow"]:
        try:
            btn = page.get_by_role("button", name=btn_text).first
            if btn.is_visible(timeout=5000):
                btn.click(timeout=5000)
                allow_clicked = True
                print(f"  Clicked: {btn_text}")
                break
        except Exception:
            pass
    
    if not allow_clicked:
        print("  No Allow button found!")
        try:
            btns = page.locator('button').all()
            for b in btns:
                if b.is_visible():
                    print(f"    Button: {b.inner_text()}")
        except:
            pass
    
    time.sleep(5)
    
    # Check if callback received
    if callback_event.wait(timeout=30):
        print(f"\n[+] Auth code received: {auth_code_container['code'][:20]}...")
        
        # Exchange token
        token_payload = {
            "clientId": client_id,
            "clientSecret": client_secret,
            "grantType": "authorization_code",
            "code": auth_code_container['code'],
            "codeVerifier": code_verifier,
            "redirectUri": redirect_uri
        }
        token_resp = requests.post(f'{OIDC_BASE}/token', json=token_payload, timeout=10)
        if token_resp.status_code == 200:
            data = token_resp.json()
            print(f"[+] Token captured! RT: {data.get('refreshToken', '')[:30]}...")
        else:
            print(f"[!] Token exchange failed: {token_resp.text[:200]}")
    else:
        print("\n[!] No auth code received")
    
    page.close()
    context.close()

server.shutdown()
