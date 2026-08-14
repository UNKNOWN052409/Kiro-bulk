"""
Kiro Web App OAuth - uses app.kiro.dev/signin with auth-code + PKCE.
This is a DIFFERENT flow than the AWS Builder ID device flow.
It uses the Kiro OAuth client with a local callback server.
"""
import sys, os, time, json, secrets, hashlib, base64, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

EMAIL = 'ax3p0kzyk6@havenhaus.in'

# Kiro OAuth config
KIRO_CLIENT_ID = "kiro-ide"  # Kiro's public client ID
KIRO_SCOPES = ["openid", "profile", "email"]
KIRO_ISSUER = "https://view.awsapps.com/start"
REDIRECT_URI = "http://localhost:3128"

def b64url(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

class CallbackHandler(BaseHTTPRequestHandler):
    auth_code_holder = {"code": None, "state": None}
    
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if 'code' in params:
            CallbackHandler.auth_code_holder['code'] = params['code'][0]
            CallbackHandler.auth_code_holder['state'] = params.get('state', [None])[0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Auth successful! You can close this window.</h1></body></html>")
        else:
            self.send_response(400)
            self.end_headers()
        
        # Shutdown server after handling
        threading.Thread(target=self.server.shutdown).start()
    
    def log_message(self, format, *args):
        pass  # Suppress logs

def main():
    print("[*] Starting Kiro web auth flow...")
    
    # Generate PKCE
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = b64url(hashlib.sha256(code_verifier.encode()).digest())
    state = secrets.token_urlsafe(32)
    
    # Start callback server
    server = HTTPServer(('127.0.0.1', 3128), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print("[*] Callback server started on port 3128")
    
    # Build auth URL - need to discover the Kiro OAuth endpoint
    # Kiro uses the AWS SSO OIDC endpoint
    import requests
    
    # First, discover the authorization endpoint from the issuer
    try:
        resp = requests.get(f"{KIRO_ISSUER}/.well-known/openid-configuration", timeout=10)
        config = resp.json()
        auth_endpoint = config.get('authorization_endpoint', '')
        token_endpoint = config.get('token_endpoint', '')
        print(f"[*] Auth endpoint: {auth_endpoint}")
        print(f"[*] Token endpoint: {token_endpoint}")
    except Exception as e:
        print(f"[!] OIDC discovery failed: {e}")
        # Use AWS SSO OIDC endpoints directly
        auth_endpoint = "https://oidc.us-east-1.amazonaws.com/authorize"
        token_endpoint = "https://oidc.us-east-1.amazonaws.com/token"
    
    # Build the authorization URL
    auth_url = (
        f"{auth_endpoint}?"
        f"response_type=code&"
        f"client_id={KIRO_CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope={' '.join(KIRO_SCOPES)}&"
        f"state={state}&"
        f"code_challenge={code_challenge}&"
        f"code_challenge_method=S256"
    )
    
    print(f"[*] Auth URL: {auth_url[:100]}...")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        print("[*] Navigating to auth URL...")
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        
        # Handle cookies
        body = page.evaluate("document.body.innerText").lower()
        if 'cookie' in body:
            try:
                page.locator('button:has-text("Decline")').first.click(timeout=3000)
            except Exception:
                try:
                    page.locator('button:has-text("Accept")').first.click(timeout=3000)
                except Exception:
                    pass
            time.sleep(3.0)
        
        # Check if we're on a login page
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] Page: {body[:200]}")
        
        # Fill email
        if 'email' in body:
            try:
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.fill(EMAIL)
                inp.press('Enter')
                print("[+] Email submitted")
                time.sleep(10.0)
            except Exception as e:
                print(f"[!] Email: {e}")
        
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] After email: {body[:200]}")
        
        # Handle name if needed
        if 'enter your name' in body:
            print("[*] On name page...")
            try:
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.type('John Smith', delay=100)
                time.sleep(1.0)
                page.locator('button:has-text("Continue")').first.click()
                time.sleep(10.0)
            except Exception as e:
                print(f"[!] Name: {e}")
        
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] After name: {body[:200]}")
        
        # OTP
        if 'verify your email' in body or 'otp' in body:
            print("[*] Getting OTP...")
            otp_arrival = time.time()
            time.sleep(15.0)
            otp = extract_otp_gmail(EMAIL, timeout=30, after_timestamp=otp_arrival)
            if otp:
                print(f"  [+] OTP: {otp}")
                try:
                    inp = page.locator('input:not([type="password"]):visible').first
                    inp.click()
                    inp.fill(otp)
                    inp.press('Enter')
                    time.sleep(8.0)
                except Exception: pass
                
                # Confirm
                try:
                    page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                    time.sleep(8.0)
                except Exception: pass
                
                # Allow
                body = page.evaluate("document.body.innerText").lower()
                if 'allow' in body:
                    try:
                        page.locator('button:has-text("Allow")').first.click(timeout=5000)
                        time.sleep(5.0)
                    except Exception: pass
        
        # Wait for redirect to callback
        print("[*] Waiting for callback...")
        for _ in range(30):
            time.sleep(2.0)
            if CallbackHandler.auth_code_holder.get('code'):
                break
        
        auth_code = CallbackHandler.auth_code_holder.get('code')
        page.close()
    
    server.shutdown()
    
    if auth_code:
        print(f"[+] Auth code received: {auth_code[:20]}...")
        
        # Exchange code for tokens
        import requests
        token_data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': REDIRECT_URI,
            'client_id': KIRO_CLIENT_ID,
            'code_verifier': code_verifier,
        }
        
        print("[*] Exchanging code for tokens...")
        try:
            resp = requests.post(token_endpoint, data=token_data, timeout=15)
            print(f"[*] Token response status: {resp.status_code}")
            print(f"[*] Token response: {resp.text[:300]}")
            
            if resp.ok:
                tokens = resp.json()
                with open('/tmp/kiro_web_tokens.json', 'w') as f:
                    json.dump(tokens, f, indent=2)
                print("[+] Tokens saved!")
            else:
                print("[!] Token exchange failed")
        except Exception as e:
            print(f"[!] Token exchange error: {e}")
    else:
        print("[!] No auth code received")

if __name__ == '__main__':
    main()
