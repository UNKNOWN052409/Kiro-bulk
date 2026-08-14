"""Test the OIDC authorize flow with a clean browser."""
import time, uuid, requests, secrets, hashlib, base64, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

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

server = HTTPServer(('127.0.0.1', 9987), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
redirect_uri = 'http://127.0.0.1:9987/oauth/callback'

# Register
reg_payload = {
    "clientName": f"kiro-clean-{uuid.uuid4().hex[:6]}",
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

print(f"[*] Auth URL: {auth_url[:120]}...")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
    print("[*] Navigating to auth URL...")
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    print(f"  URL after nav: {page.url[:120]}")
    
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
    
    body = page.evaluate("document.body.innerText")
    print(f"\n[*] Page body (after cookie dismiss):")
    print(f"    {body[:400]}")
    print(f"\n[*] URL: {page.url[:150]}")
    
    page.close()
    context.close()

server.shutdown()
