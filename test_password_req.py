"""Test what password requirements AWS Builder ID accepts."""
import sys, time, uuid, requests, secrets, hashlib, base64, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

sys.path.insert(0, '/home/ubuntu/kiro-gen')
from extract_otp_v3 import extract_otp_gmail_v3

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

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

server = HTTPServer(('127.0.0.1', 9988), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
redirect_uri = 'http://127.0.0.1:9988/oauth/callback'

reg_payload = {
    "clientName": f"kiro-test-{uuid.uuid4().hex[:6]}",
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

# Test email and password
test_email = "pwtest001@havenhaus.in"
# Simple password that meets AWS requirements
test_password = "TestPass123!"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
    print("[*] Navigating to auth URL...")
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    
    # Wait for render
    for i in range(60):
        time.sleep(2)
        try:
            ready = page.evaluate("document.readyState")
            if ready == 'complete':
                body = page.evaluate("document.body ? document.body.innerText : ''")
                if len(body) > 50:
                    break
        except:
            pass
    
    # Dismiss cookies
    try:
        for btn_text in ["Decline", "Dismiss"]:
            btns = page.get_by_role("button", name=btn_text, exact=True).all()
            for btn in btns:
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    time.sleep(1)
    except:
        pass
    time.sleep(3)
    
    # Get body
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] Page body:")
    print(f"    {body[:500]}")
    
    # Try to fill password
    try:
        pw_inputs = page.locator('input[type="password"]').all()
        visible_pw = [inp for inp in pw_inputs if inp.is_visible()]
        print(f"\n[*] Visible password inputs: {len(visible_pw)}")
        for inp in visible_pw:
            ph = inp.get_attribute('placeholder')
            print(f"    placeholder: {ph}")
        
        if visible_pw:
            visible_pw[0].fill(test_password)
            if len(visible_pw) > 1:
                visible_pw[1].fill(test_password)
            time.sleep(1)
            page.get_by_role("button", name="Continue").first.click(timeout=5000)
            print(f"    Password filled and submitted")
    except Exception as e:
        print(f"    Error: {e}")
    
    time.sleep(15)
    # Wait for next page
    for i in range(30):
        time.sleep(2)
        try:
            ready = page.evaluate("document.readyState")
            if ready == 'complete':
                body = page.evaluate("document.body ? document.body.innerText : ''")
                if len(body) > 50:
                    break
        except:
            pass
    
    # Dismiss cookies again
    try:
        for btn_text in ["Decline", "Dismiss"]:
            btns = page.get_by_role("button", name=btn_text, exact=True).all()
            for btn in btns:
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    time.sleep(1)
    except:
        pass
    time.sleep(3)
    
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] After password submit:")
    print(f"    {body[:500]}")
    
    # Check for error
    if "doesn't quite match" in body or "does not match" in body:
        print("\n[!] PASSWORD REJECTED!")
        print("    Trying different password format...")
        
        # Try a simpler password
        test_password2 = "Test1234!"
        try:
            pw_inputs = page.locator('input[type="password"]').all()
            visible_pw = [inp for inp in pw_inputs if inp.is_visible()]
            if visible_pw:
                visible_pw[0].fill(test_password2)
                if len(visible_pw) > 1:
                    visible_pw[1].fill(test_password2)
                time.sleep(1)
                page.get_by_role("button", name="Continue").first.click(timeout=5000)
                print(f"    New password submitted: {test_password2}")
        except Exception as e:
            print(f"    Error: {e}")
        
        time.sleep(15)
        for i in range(30):
            time.sleep(2)
            try:
                ready = page.evaluate("document.readyState")
                if ready == 'complete':
                    body = page.evaluate("document.body ? document.body.innerText : ''")
                    if len(body) > 50:
                        break
            except:
                pass
        try:
            for btn_text in ["Decline", "Dismiss"]:
                btns = page.get_by_role("button", name=btn_text, exact=True).all()
                for btn in btns:
                    if btn.is_visible(timeout=500):
                        btn.click(timeout=1000)
                        time.sleep(1)
        except:
            pass
        time.sleep(3)
        
        body = page.evaluate("document.body.innerText")
        print(f"\n[*] After second password attempt:")
        print(f"    {body[:500]}")
    
    page.close()
    context.close()

server.shutdown()
