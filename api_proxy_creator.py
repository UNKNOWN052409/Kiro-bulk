"""
Kiro AI Account Creator - API Proxy Approach
- Browser WITHOUT proxy for everything (SPA renders fast on datacenter IP)
- Intercept ONLY profile.aws.amazon.com API calls (POST to /api/*) and replay through residential proxy
- Static assets (JS, CSS, images) load directly from datacenter IP (fast)
"""

import uuid, secrets, hashlib, base64, requests, json, time, socket, threading, http.server
from urllib.parse import quote
from playwright.sync_api import sync_playwright

# Config
REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"]
CALLBACK_PORT = 9997
DIRECTORY_ID = 'd-9067642ac7'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

# ProxyRise config
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_SESSION_ID = str(uuid.uuid4().int % (10**9))
PROXY_URL = f'socks5://res-us-sid-{PROXY_SESSION_ID}:{PROXYRISE_API_KEY}@gw.proxyrise.com:443'
LOCAL_PROXY_PORT = 8899

# OTP email
OTP_EMAIL = 'anshika31618@gmail.com'
OTP_DOMAIN = 'havenhaus.in'

# First names and last names for realistic names
FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'Mia', 'James', 'Charlotte', 'Benjamin', 'Amelia', 'Lucas', 'Harper', 'Henry', 'Evelyn', 'Alexander',
               'Abigail', 'Michael', 'Emily', 'Elijah', 'Elizabeth', 'Daniel', 'Mila', 'Matthew', 'Ella', 'Aiden']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
              'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin',
              'Lee', 'Perez', 'Thompson', 'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson']


class LocalProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP proxy handler that forwards to SOCKS5 residential proxy."""
    
    def do_CONNECT(self):
        """Handle HTTPS CONNECT requests."""
        import socks, socket as socklib
        dest_host, dest_port = self.path.split(':')
        dest_port = int(dest_port)
        
        try:
            # Connect to SOCKS5 proxy
            s = socks.socksocket()
            s.set_proxy(socks.SOCKS5, 'gw.proxyrise.com', 443, 
                       username=f'res-us-sid-{PROXY_SESSION_ID}:{PROXYRISE_API_KEY}',
                       rdns=True)
            s.connect((dest_host, dest_port))
            
            self.send_response(200)
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            # Create tunnel between client and target
            def forward(src, dst):
                try:
                    while True:
                        data = src.recv(65536)
                        if not data:
                            break
                        dst.sendall(data)
                except:
                    pass
                finally:
                    try: src.close()
                    except: pass
                    try: dst.close()
                    except: pass
            
            threading.Thread(target=forward, args=(s, self.connection), daemon=True).start()
            threading.Thread(target=forward, args=(self.connection, s), daemon=True).start()
        except Exception as e:
            self.send_error(502, f'Bad Gateway: {e}')


def start_local_proxy():
    """Start the local HTTP→SOCKS5 proxy in a background thread."""
    server = http.server.HTTPServer(('127.0.0.1', LOCAL_PROXY_PORT), LocalProxyHandler)
    server.daemon_threads = True
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.5)
    return server


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handle OAuth callback to capture auth code."""
    captured_code = None
    captured_state = None
    
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        CallbackHandler.captured_code = params.get('code', [None])[0]
        CallbackHandler.captured_state = params.get('state', [None])[0]
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>Authorization received</h1><p>You can close this tab.</p></body></html>')
    
    def log_message(self, format, *args):
        pass  # Suppress logging


def extract_otp_from_gmail(email_user, email_pass):
    """Extract OTP from Gmail."""
    import imaplib, email as email_lib, re
    import base64
    
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_user, email_pass)
        mail.select('inbox')
        
        # Search for recent emails
        status, messages = mail.search(None, '(FROM "no-reply@amazon.com" OR FROM "amazon.com")')
        
        if status != 'OK' or not messages[0]:
            mail.logout()
            return None
        
        msg_ids = messages[0].split()
        
        for msg_id in reversed(msg_ids[-5:]):  # Check last 5 emails
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
            
            raw_email = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw_email)
            
            # Check if from Amazon
            from_addr = msg.get('From', '')
            if 'amazon' not in from_addr.lower():
                continue
            
            # Extract body
            otp = None
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain':
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        # Look for OTP pattern (6-digit code)
                        match = re.search(r'\b(\d{6})\b', body)
                        if match:
                            otp = match.group(1)
                            break
                    elif content_type == 'text/html':
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        # Remove HTML tags
                        clean = re.sub(r'<[^>]+>', ' ', body)
                        match = re.search(r'\b(\d{6})\b', clean)
                        if match:
                            otp = match.group(1)
                            break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                match = re.search(r'\b(\d{6})\b', body)
                if match:
                    otp = match.group(1)
            
            if otp:
                mail.logout()
                return otp
        
        mail.logout()
        return None
    except Exception as e:
        print(f"    [!] Gmail error: {e}")
        return None


def main():
    import random
    
    print("=" * 70)
    print("Kiro AI Account Creator - API Proxy Approach")
    print("=" * 70)
    
    # Generate random name and email
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email = f'{random_suffix}@{OTP_DOMAIN}'
    
    print(f"\nCreating: {full_name} <{email}>")
    print(f"Proxy session: {PROXY_SESSION_ID}")
    print()
    
    # Start local proxy (HTTP→SOCKS5)
    print("[0] Starting local proxy wrapper...")
    local_proxy = start_local_proxy()
    print(f"    Local proxy on :{LOCAL_PROXY_PORT} → SOCKS5 residential")
    
    # Register OIDC client
    print("[1] Registering OIDC client...")
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
    print(f"    Client ID: {client_id}")
    
    # PKCE
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_urlsafe(16)
    redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
    
    scopes_encoded = ' '.join(GRANT_SCOPES)
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
                f'&state={state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    # Start callback server
    CallbackHandler.captured_code = None
    CallbackHandler.captured_state = None
    callback_server = http.server.HTTPServer(('127.0.0.1', CALLBACK_PORT), CallbackHandler)
    callback_server.daemon_threads = True
    callback_thread = threading.Thread(target=callback_server.serve_forever, daemon=True)
    callback_thread.start()
    print(f"    Callback server on :{CALLBACK_PORT}")
    
    # Launch browser WITHOUT proxy
    print("[2] Launching browser (no proxy)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=UA, locale='en-US')
        page = context.new_page()
        page.set_default_timeout(60000)
        page.set_default_navigation_timeout(60000)
        
        # Track API calls for debugging
        api_calls = []
        def on_request(request):
            if 'profile.aws.amazon.com' in request.url and '/api/' in request.url:
                api_calls.append({'url': request.url, 'method': request.method, 'time': time.time()})
                print(f"    [API-REQ] {request.method} {request.url.split('amazon.com')[1][:60]}")
        
        def on_response(response):
            if 'profile.aws.amazon.com' in response.url and '/api/' in response.url:
                try:
                    body = response.json()
                    step = body.get('stepId', 'N/A')
                    error = body.get('message', {}).get('errorCode', '')
                    wsh = body.get('workflowStateHandle', '')
                    print(f"    [API-RESP] step={step}, err={error}, wsh={wsh[:8]}...")
                except:
                    pass
        
        page.on('request', on_request)
        page.on('response', on_response)
        
        # Navigate to OIDC authorize
        print("[3] Navigating to OIDC authorize...")
        page.goto(auth_url, wait_until='domcontentloaded', timeout=60000)
        time.sleep(3)
        
        # Wait for email form
        print("[4] Waiting for email form...")
        for i in range(20):
            time.sleep(1)
            try:
                body = page.evaluate('document.body.innerText')
                if 'email' in body.lower() and 'continue' in body.lower():
                    print(f"    Form ready at {i}s")
                    break
            except:
                pass
        
        # Fill email and submit
        print("[5] Filling email...")
        email_input = page.locator('input[type="email"]').first
        email_input.fill(email)
        time.sleep(0.5)
        continue_btn = page.locator('button:has-text("Continue")').first
        continue_btn.click()
        print("    Email submitted")
        
        # Wait for name page on profile.aws.amazon.com
        print("[6] Waiting for name page on profile.aws.amazon.com...")
        for i in range(30):
            time.sleep(1)
            try:
                url = page.url
                body = page.evaluate('document.body.innerText')
                if 'profile.aws.amazon.com' in url and ('enter your name' in body.lower() or 'error' not in body.lower()[:50]):
                    print(f"    Name page at {i}s!")
                    print(f"    URL: {url[:80]}")
                    break
            except:
                pass
        
        # Dismiss cookie dialog
        try:
            accept_btn = page.locator('button:has-text("Accept")').first
            if accept_btn.is_visible(timeout=3000):
                accept_btn.click()
                time.sleep(1)
                print("    Cookie dialog dismissed")
        except:
            pass
        
        # Fill name
        print("[7] Filling name...")
        name_input = page.locator('input[placeholder]').first
        name_input.fill(full_name)
        time.sleep(1)
        
        # Click Continue - THIS WILL GO THROUGH DATACENTER IP AND GET ERR-837
        print("[8] Clicking Continue (expecting ERR-837)...")
        continue_btn2 = page.locator('button:has-text("Continue")').first
        continue_btn2.click()
        time.sleep(5)
        
        body = page.evaluate('document.body.innerText')
        print(f"    After Continue: {body[:80]}")
        
        # Check if we got ERR-837
        if 'err-837' in body.lower():
            print("\n    !!! Got ERR-837 as expected on datacenter IP !!!")
            print("    Now the question is: can we intercept just this API call and replay through proxy?")
            
            # The page shows error but might allow retry
            # Let's check if there's a "Try again" or similar button
            try:
                retry_btn = page.locator('button:has-text("Try")').first
                if retry_btn.is_visible(timeout=3000):
                    print("    Found retry button")
                else:
                    print("    No retry button found")
            except:
                print("    No retry button")
        
        browser.close()
    
    callback_server.shutdown()
    print("\nDone!")


if __name__ == '__main__':
    main()
