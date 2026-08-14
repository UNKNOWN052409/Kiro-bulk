"""
Kiro AI Account Creator - Final Hybrid Approach
- Browser WITHOUT proxy for everything (SPA renders fast)
- Intercept send-otp POST on profile.aws.amazon.com and replay through residential proxy
- All other requests go directly (datacenter IP)
"""

import uuid, secrets, hashlib, base64, requests, json, time, socket, threading, http.server, random
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
LOCAL_PROXY_PORT = 8899

# Names
FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'Mia', 'James', 'Charlotte', 'Benjamin', 'Amelia', 'Lucas', 'Harper', 'Henry', 'Evelyn', 'Alexander',
               'Abigail', 'Michael', 'Emily', 'Elijah', 'Elizabeth', 'Daniel', 'Mila', 'Matthew', 'Ella', 'Aiden',
               'Sebastian', 'Jack', 'Owen', 'Theodore', 'Aria', 'Scarlett', 'Victoria', 'Madison', 'Luna', 'Grace']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
              'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin',
              'Lee', 'Perez', 'Thompson', 'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson',
              'Walker', 'Young', 'Allen', 'King', 'Wright', 'Scott', 'Torres', 'Nguyen', 'Hill', 'Flores']


class Socks5ConnectHandler(http.server.BaseHTTPRequestHandler):
    """HTTP proxy handler that forwards CONNECT to SOCKS5 residential proxy."""
    
    def do_CONNECT(self):
        import socks
        dest_host, dest_port = self.path.split(':')
        dest_port = int(dest_port)
        
        try:
            s = socks.socksocket()
            s.set_proxy(socks.SOCKS5, 'gw.proxyrise.com', 443,
                       username=f'res-us-sid-{PROXY_SESSION_ID}',
                       password=PROXYRISE_API_KEY,
                       rdns=True)
            s.settimeout(30)
            s.connect((dest_host, dest_port))
            
            self.send_response(200)
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
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
    
    def log_message(self, format, *args):
        pass


def start_local_proxy():
    server = http.server.HTTPServer(('127.0.0.1', LOCAL_PROXY_PORT), Socks5ConnectHandler)
    server.daemon_threads = True
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.5)
    return server


class CallbackHandler(http.server.BaseHTTPRequestHandler):
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
        self.wfile.write(b'<html><body><h1>OK</h1></body></html>')
    
    def log_message(self, format, *args):
        pass


def extract_otp():
    """Extract OTP from Gmail."""
    import imaplib, email as email_lib, re
    
    email_user = 'anshika31618@gmail.com'
    email_pass = 'hlcv eobi tfwh terw'
    
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_user, email_pass)
        mail.select('inbox')
        
        status, messages = mail.search(None, '(FROM "amazon.com" OR FROM "no-reply@amazon.com")')
        if status != 'OK' or not messages[0]:
            mail.logout()
            return None
        
        msg_ids = messages[0].split()
        for msg_id in reversed(msg_ids[-5:]):
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
            
            msg = email_lib.message_from_bytes(msg_data[0][1])
            from_addr = msg.get('From', '')
            if 'amazon' not in from_addr.lower():
                continue
            
            otp = None
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct in ('text/plain', 'text/html'):
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        if ct == 'text/html':
                            body = re.sub(r'<[^>]+>', ' ', body)
                        match = re.search(r'\b(\d{6})\b', body)
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


def replay_through_proxy(method, url, headers, body):
    """Replay an HTTP request through the SOCKS5 residential proxy using curl_cffi with Chrome impersonation."""
    from curl_cffi import requests as cffi_requests
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    
    # Build the proxy URL for curl
    # curl supports socks5h:// which resolves DNS through the proxy
    proxy_url = f"socks5h://res-us-sid-{PROXY_SESSION_ID}:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
    
    try:
        if method == 'POST':
            resp = cffi_requests.post(
                url,
                headers=headers,
                data=body.encode('utf-8') if isinstance(body, str) else body,
                proxy=proxy_url,
                impersonate='chrome131',
                timeout=30
            )
        else:
            resp = cffi_requests.get(
                url,
                headers=headers,
                proxy=proxy_url,
                impersonate='chrome131',
                timeout=30
            )
        
        # Convert to raw response format for parse_http_response
        status = resp.status_code
        resp_headers = dict(resp.headers)
        body_text = resp.text
        
        return status, resp_headers, body_text
    except Exception as e:
        print(f"    [PROXY] curl_cffi error: {e}")
        # Fallback to raw socket approach
        return _fallback_replay(method, url, headers, body)


def _fallback_replay(method, url, headers, body):
    """Fallback: raw socket replay through SOCKS5 proxy."""
    import socks
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 443
    
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, 'gw.proxyrise.com', 443,
               username=f'res-us-sid-{PROXY_SESSION_ID}',
               password=PROXYRISE_API_KEY,
               rdns=True)
    s.settimeout(30)
    s.connect((host, port))
    
    import ssl
    ctx = ssl.create_default_context()
    ss = ctx.wrap_socket(s, server_hostname=host)
    
    body_bytes = body.encode('utf-8') if isinstance(body, str) else body
    request = f"{method} {parsed.path} HTTP/1.1\r\nHost: {host}\r\n"
    for k, v in headers.items():
        if k.lower() not in ('content-length', 'host'):
            request += f"{k}: {v}\r\n"
    request += f"Content-Length: {len(body_bytes)}\r\nConnection: close\r\n\r\n"
    ss.sendall(request.encode('utf-8'))
    ss.sendall(body_bytes)
    
    response_data = b''
    while True:
        try:
            chunk = ss.recv(65536)
            if not chunk:
                break
            response_data += chunk
        except:
            break
    ss.close()
    
    return parse_http_response(response_data)


def parse_http_response(data):
    """Parse raw HTTP response into status code, headers, body."""
    if not data:
        return 502, {}, ''
    
    try:
        header_end = data.find(b'\r\n\r\n')
        if header_end == -1:
            header_end = data.find(b'\n\n')
            sep = b'\n\n'
        else:
            sep = b'\r\n\r\n'
        
        header_part = data[:header_end].decode('utf-8', errors='ignore')
        body = data[header_end + len(sep):].decode('utf-8', errors='ignore')
        
        lines = header_part.split('\r\n')
        status_line = lines[0]
        status_code = int(status_line.split(' ')[1])
        
        headers = {}
        for line in lines[1:]:
            if ':' in line:
                k, v = line.split(':', 1)
                headers[k.strip()] = v.strip()
        
        return status_code, headers, body
    except:
        return 502, {}, ''


def main():
    print("=" * 70)
    print("Kiro AI Account Creator - Final Hybrid (send-otp via proxy)")
    print("=" * 70)
    
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email = f'{random_suffix}@havenhaus.in'
    password = f'Kiro{random_suffix[:4]}!2026'
    
    print(f"\nCreating: {full_name} <{email}>")
    print(f"Password: {password}")
    print(f"Proxy session: {PROXY_SESSION_ID}")
    print()
    
    # Start local proxy
    print("[0] Starting local SOCKS5 proxy wrapper...")
    local_proxy = start_local_proxy()
    
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
    
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_urlsafe(16)
    redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={quote(redirect_uri)}&scopes={quote(" ".join(GRANT_SCOPES))}'
                f'&state={state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    # Start callback server
    CallbackHandler.captured_code = None
    callback_server = http.server.HTTPServer(('127.0.0.1', CALLBACK_PORT), CallbackHandler)
    callback_server.daemon_threads = True
    threading.Thread(target=callback_server.serve_forever, daemon=True).start()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=UA, locale='en-US')
        page = context.new_page()
        page.set_default_timeout(60000)
        page.set_default_navigation_timeout(60000)
        
        # ===== INTERCEPT send-otp and replay through proxy =====
        print("[2] Setting up send-otp interception...")
        
        send_otp_intercepted = {'done': False, 'response': None}
        
        def handle_send_otp(route, request):
            """Intercept send-otp and replay through residential proxy."""
            if send_otp_intercepted['done']:
                route.continue_()
                return
            
            url = request.url
            if '/api/send-otp' in url:
                send_otp_intercepted['done'] = True
                print(f"\n    [PROXY] Intercepting send-otp!")
                print(f"    [PROXY] URL: {url}")
                
                # Get request headers (excluding host)
                headers = dict(request.headers)
                headers.pop('Host', None)
                headers.pop('Content-Length', None)
                
                body = request.post_data or ''
                
                # Log full request details for debugging
                print(f"    [PROXY] Headers: {json.dumps({k:v for k,v in headers.items()}, indent=2)[:500]}")
                print(f"    [PROXY] Body length: {len(body)}")
                print(f"    [PROXY] Body (first 500): {body[:500]}")
                
                # Replay through residential proxy
                print(f"    [PROXY] Replaying through SOCKS5 residential proxy...")
                status, resp_headers, resp_body = replay_through_proxy('POST', url, headers, body)
                
                print(f"    [PROXY] Response: {status}")
                print(f"    [PROXY] Body: {resp_body[:200]}")
                
                if status == 200:
                    # Check if the response is valid JSON
                    try:
                        json.loads(resp_body)
                        print(f"    [PROXY] SUCCESS - forwarding response to browser")
                        route.fulfill(status=status, content_type='application/json', body=resp_body)
                        return
                    except:
                        pass
                
                # If proxy replay failed, still forward what we got
                if resp_body:
                    route.fulfill(status=status, content_type='application/json', body=resp_body)
                else:
                    route.fulfill(status=502, content_type='text/plain', body='Proxy replay failed')
            else:
                route.continue_()
        
        page.route('**/profile.aws.amazon.com/**', handle_send_otp)
        
        # Navigate
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
        
        # Fill email
        print("[5] Filling email...")
        email_input = page.locator('input[type="email"]').first
        email_input.fill(email)
        time.sleep(0.5)
        continue_btn = page.locator('button:has-text("Continue")').first
        continue_btn.click()
        print("    Email submitted")
        
        # Wait for name page
        print("[6] Waiting for name page...")
        for i in range(30):
            time.sleep(1)
            try:
                url = page.url
                body = page.evaluate('document.body.innerText')
                if 'profile.aws.amazon.com' in url and len(body) > 20:
                    print(f"    Profile page at {i}s: {body[:50]}")
                    if 'enter your name' in body.lower():
                        break
            except:
                pass
        
        time.sleep(3)
        
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
        print(f"    Name filled: {full_name}")
        
        # Click Continue - this triggers send-otp which will be intercepted
        print("[8] Clicking Continue (send-otp will go through proxy)...")
        continue_btn2 = page.locator('button:has-text("Continue")').first
        continue_btn2.click()
        
        # Wait for the intercepted response to process
        print("[9] Waiting for send-otp proxy response...")
        for i in range(20):
            time.sleep(1)
            try:
                body = page.evaluate('document.body.innerText')
                url = page.url
                if 'err-837' not in body.lower() and len(body) > 10:
                    print(f"    [{i}s] Body: {body[:80]}")
                    if 'otp' in body.lower() or 'code' in body.lower() or 'verification' in body.lower():
                        print("    OTP step reached!")
                        break
                elif 'err-837' in body.lower():
                    print(f"    [{i}s] Still ERR-837: {body[:60]}")
            except:
                pass
        
        time.sleep(2)
        
        # Check current state
        body = page.evaluate('document.body.innerText')
        url = page.url
        print(f"\n    Current URL: {url[:80]}")
        print(f"    Current body: {body[:100]}")
        
        # Take screenshot
        try:
            page.screenshot(path='/home/ubuntu/kiro-gen/final_state.png', timeout=10000)
        except:
            pass
        
        browser.close()
    
    callback_server.shutdown()
    print("\nDone!")


if __name__ == '__main__':
    main()
