"""
Kiro AI Account Creator - HTTP Forward Proxy Mode
Uses HTTP forward proxy on port 8080 for API calls through residential IP.
Browser loads pages directly (fast), API calls go through proxy (residential IP).
"""

import uuid, secrets, hashlib, base64, time, random, re, json, threading, http.server
from urllib.parse import quote, urlparse, parse_qs
from playwright.sync_api import sync_playwright
import requests as req
import socket

# Configuration
CALLBACK_PORT = 9997
DIRECTORY_ID = 'd-9067642ac7'
UAMOBILE = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

# ProxyRise config
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXYRISE_AUTH = base64.b64encode(f'res-us:{PROXYRISE_API_KEY}'.encode()).decode()
PROXY_HOST = 'gw.proxyrise.com'
PROXY_PORT = 8080  # HTTP forward proxy port

# Gmail OTP config
GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_PASS = 'hlcv eobi tfwh terw'

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'James', 'Charlotte', 'Benjamin', 'Lucas', 'Harper', 'Henry', 'Alexander', 'Sebastian', 'Jack', 'Owen',
               'Daniel', 'Matthew', 'Anthony', 'Mark', 'Steven', 'Andrew', 'Paul', 'Joshua', 'Kenneth', 'Brian']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Martinez', 'Wilson',
              'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Allen', 'King', 'Scott']

_callback_code = None
_callback_event = threading.Event()


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _callback_code, _callback_event
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        code = params.get('code', [None])[0]
        if code:
            _callback_code = code
            _callback_event.set()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>OK</h1></body></html>')
    def log_message(self, format, *args):
        pass


def start_callback_server():
    global _callback_code, _callback_event
    _callback_code = None
    _callback_event.clear()
    server = http.server.HTTPServer(('127.0.0.1', CALLBACK_PORT), CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def forward_proxy_request(method, url, headers=None, data=None):
    """Send a request through the HTTP forward proxy on port 8080."""
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path
    if parsed.query:
        path += '?' + parsed.query
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    sock.connect((PROXY_HOST, PROXY_PORT))
    
    # Build the forward proxy request
    request = f"{method} {url} HTTP/1.1\r\n"
    request += f"Host: {host}\r\n"
    request += f"Proxy-Authorization: Basic {PROXYRISE_AUTH}\r\n"
    request += "Connection: close\r\n"
    
    # Add custom headers
    if headers:
        for k, v in headers.items():
            if k.lower() not in ('host', 'connection', 'proxy-authorization'):
                request += f"{k}: {v}\r\n"
    
    # Add content-type and body for POST
    if data:
        request += f"Content-Type: application/json\r\n"
        request += f"Content-Length: {len(data)}\r\n"
        request += "\r\n"
        request += data
    else:
        request += "\r\n"
    
    sock.sendall(request.encode())
    
    response = b''
    while True:
        try:
            chunk = sock.recv(65536)
            if not chunk:
                break
            response += chunk
        except:
            break
    
    sock.close()
    
    # Parse response
    text = response.decode('utf-8', errors='ignore')
    if not text:
        return 0, ''
    
    # Split headers from body
    parts = text.split('\r\n\r\n', 1)
    header_section = parts[0]
    body = parts[1] if len(parts) > 1 else ''
    
    # Parse status line
    first_line = header_section.split('\r\n')[0] if header_section else ''
    try:
        status_code = int(first_line.split(' ')[1])
    except (IndexError, ValueError):
        # If we can't parse the status, return 0
        return 0, body
    
    return status_code, body


def test_proxy():
    """Test the HTTP forward proxy."""
    print("    Testing proxy...")
    try:
        status, body = forward_proxy_request('GET', 'https://api.ipquery.io/?format=json')
        if status == 200:
            data = json.loads(body)
            ip = data.get('ip', 'Unknown')
            loc = data.get('location', {})
            risk = data.get('risk', {})
            print(f"    Proxy IP: {ip} ({loc.get('country')}, {loc.get('city')})")
            print(f"    Mobile: {risk.get('is_mobile')}, Datacenter: {risk.get('is_datacenter')}, Proxy: {risk.get('is_proxy')}")
            return True, ip
    except Exception as e:
        print(f"    Proxy test failed: {e}")
    return False, None


def extract_otp():
    import imaplib
    import email as email_lib
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_USER, GMAIL_PASS)
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
        print(f"    [Gmail] Error: {e}")
        return None


def create_account():
    """Create a single Kiro AI account with proxy for API calls."""
    global _callback_code, _callback_event
    
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email = f'{random_suffix}@havenhaus.in'
    password = f'Kiro{random_suffix[:4]}!2026'
    
    account_info = {
        'email': email,
        'name': full_name,
        'password': password,
        'status': 'pending'
    }
    
    print(f"\n{'='*60}")
    print(f"Creating: {full_name} <{email}>")
    print(f"Password: {password}")
    print(f"{'='*60}\n")
    
    # Test proxy first
    proxy_ok, proxy_ip = test_proxy()
    if not proxy_ok:
        print("    [!] Proxy not working!")
        account_info['status'] = 'failed_proxy'
        return account_info
    
    # Start callback server
    callback_server = start_callback_server()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=UAMOBILE,
            locale='en-US',
            timezone_id='America/New_York',
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        
        # Intercept API calls and replay through proxy
        def on_request(route):
            url = route.request.url
            if '/api/execute' in url:
                # Replay through proxy
                method = route.request.method
                headers = route.request.headers
                post_data = route.request.post_data
                
                try:
                    status, body = forward_proxy_request(method, url, headers=headers, data=post_data)
                    # Return the proxied response to the browser
                    route.fulfill(
                        status=status,
                        content_type='application/json',
                        body=body
                    )
                    print(f"    [Proxy] {method} {url.split('execute')[1][:30]} -> {status}")
                except Exception as e:
                    print(f"    [Proxy] Error: {e}, falling back to direct")
                    route.continue_()
            else:
                route.continue_()
        
        page.route('**/api/execute**', on_request)
        
        # Track API responses
        api_responses = []
        def on_response(response):
            url = response.url
            if '/api/execute' in url:
                try:
                    body = response.json()
                    step = body.get('stepId', '')
                    api_responses.append({'step': step, 'status': response.status})
                except:
                    pass
        
        page.on('response', on_response)
        
        # Register OIDC client (direct, not through proxy)
        print("[1] Registering OIDC client...")
        reg_resp = req.post('https://oidc.us-east-1.amazonaws.com/client/register', json={
            'clientName': f'kiro-{uuid.uuid4().hex[:8]}',
            'clientType': 'public',
            'scopes': ['codewhisperer:completions', 'codewhisperer:analysis', 'codewhisperer:conversations'],
            'grantTypes': ['authorization_code', 'refresh_token'],
            'redirectUris': [f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'],
            'issuerUrl': 'https://view.awsapps.com/start'
        }, timeout=15)
        client_id = reg_resp.json()['clientId']
        print(f"    Client ID: {client_id}")
        
        # Generate PKCE challenge
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b'=').decode()
        
        # Navigate to OIDC authorize
        print("[2] Navigating to OIDC authorize...")
        auth_url = (f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code'
                    f'&client_id={client_id}'
                    f'&redirect_uri={quote(f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback")}'
                    f'&scopes={quote("codewhisperer:completions codewhisperer:analysis codewhisperer:conversations")}'
                    f'&state={secrets.token_urlsafe(16)}'
                    f'&code_challenge={code_challenge}'
                    f'&code_challenge_method=S256')
        page.goto(auth_url, wait_until='domcontentloaded', timeout=90000)
        print(f"    URL: {page.url[:80]}")
        
        # Wait for email form
        print("[3] Waiting for email form...")
        email_submitted = False
        for i in range(45):
            if email_submitted:
                break
            time.sleep(2)
            try:
                email_input = page.locator('input[type="email"]').first
                if email_input.is_visible(timeout=2000):
                    print(f"    Email form ready at {i*2}s!")
                    email_input.click()
                    time.sleep(random.uniform(0.3, 0.7))
                    email_input.fill(email)
                    time.sleep(random.uniform(0.5, 1.0))
                    print(f"    Email filled: {email}")
                    
                    btn = page.locator('button:has-text("Continue")').first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        email_submitted = True
                        print(f"    Email submitted at {i*2}s!")
                        time.sleep(3)
                        break
            except:
                pass
        
        if not email_submitted:
            print("    [!] Email form not found!")
            account_info['status'] = 'failed_email'
            browser.close()
            callback_server.shutdown()
            return account_info
        
        # Wait for name form
        print("[4] Waiting for name form...")
        name_submitted = False
        for i in range(90):
            if name_submitted:
                break
            time.sleep(2)
            try:
                text = page.inner_text('body')
                if 'enter your name' in text.lower():
                    print(f"    Name form detected at {i*2}s!")
                    
                    name_input = page.locator('input[type="text"]').first
                    if name_input.is_visible(timeout=3000):
                        name_input.click()
                        time.sleep(random.uniform(0.3, 0.5))
                        name_input.fill(full_name)
                        time.sleep(random.uniform(0.5, 1.0))
                        print(f"    Name filled: {full_name}")
                        
                        btn = page.locator('button:has-text("Continue")').first
                        if btn.is_visible(timeout=2000):
                            btn.click()
                            print(f"    Name submitted at {i*2}s!")
                            time.sleep(5)
                            
                            after_text = page.inner_text('body')
                            if 'err-837' in after_text.lower():
                                print("    [!] ERR-837 - retrying once...")
                                time.sleep(3)
                                name_input.fill(full_name)
                                time.sleep(0.5)
                                btn = page.locator('button:has-text("Continue")').first
                                if btn.is_visible(timeout=2000):
                                    btn.click()
                                    time.sleep(5)
                                    after_text2 = page.inner_text('body')
                                    if 'err-837' not in after_text2.lower():
                                        name_submitted = True
                                        print("    Name submission SUCCESS on retry!")
                                    else:
                                        print("    [!] ERR-837 again")
                                        account_info['status'] = 'failed_err837'
                                        browser.close()
                                        callback_server.shutdown()
                                        return account_info
                            else:
                                name_submitted = True
                                print("    Name submission SUCCESS!")
                            break
            except Exception as e:
                if i == 44:
                    print(f"    [!] Error: {e}")
        
        if not name_submitted:
            print("    [!] Name form not found or submission failed!")
            account_info['status'] = 'failed_name'
            page.screenshot(path='/home/ubuntu/kiro-gen/debug_name.png')
            browser.close()
            callback_server.shutdown()
            return account_info
        
        # Wait for OTP form
        print("[5] Waiting for OTP form...")
        otp_submitted = False
        for i in range(60):
            if otp_submitted:
                break
            time.sleep(2)
            try:
                text = page.inner_text('body')
                if any(kw in text.lower() for kw in ['one-time', 'otp', 'verification code', 'enter the code']) or \
                   ('code' in text.lower() and 'email' in text.lower()):
                    print(f"    OTP form detected at {i*2}s")
                    
                    otp = None
                    for j in range(15):
                        otp = extract_otp()
                        if otp:
                            break
                        time.sleep(3)
                    
                    if otp:
                        print(f"    OTP: {otp}")
                        for sel in ['input[inputmode="numeric"]', 'input[type="text"]']:
                            inputs = page.locator(sel).all()
                            for inp in inputs:
                                if inp.is_visible() and 'password' not in (inp.get_attribute('type') or ''):
                                    try:
                                        inp.fill(otp)
                                        time.sleep(0.3)
                                        btn = page.locator('button:has-text("Continue"), button:has-text("Verify")').first
                                        if btn.is_visible(timeout=1000):
                                            btn.click()
                                            otp_submitted = True
                                            print("    OTP submitted!")
                                            time.sleep(3)
                                            break
                                    except:
                                        continue
                            if otp_submitted:
                                break
                    else:
                        print("    [!] OTP not found")
                    
                    if otp_submitted:
                        break
            except:
                pass
        
        if not otp_submitted:
            print("    [!] OTP failed!")
            account_info['status'] = 'failed_otp'
            browser.close()
            callback_server.shutdown()
            return account_info
        
        # Wait for password form
        print("[6] Waiting for password form...")
        pw_submitted = False
        for i in range(30):
            if pw_submitted:
                break
            time.sleep(2)
            try:
                text = page.inner_text('body')
                if 'password' in text.lower() and ('create' in text.lower() or 'set' in text.lower()):
                    print(f"    Password form detected at {i*2}s")
                    pw_inputs = page.locator('input[type="password"]').all()
                    visible_pw = [inp for inp in pw_inputs if inp.is_visible()]
                    if visible_pw:
                        visible_pw[0].fill(password)
                        time.sleep(0.3)
                        if len(visible_pw) >= 2:
                            visible_pw[1].fill(password)
                            time.sleep(0.3)
                        btn = page.locator('button:has-text("Create"), button[type="submit"]').first
                        if btn.is_visible(timeout=1000):
                            btn.click()
                            pw_submitted = True
                            print("    Password submitted!")
                            break
            except:
                pass
        
        if not pw_submitted:
            print("    [!] Password form not found!")
            account_info['status'] = 'failed_password'
            browser.close()
            callback_server.shutdown()
            return account_info
        
        # Wait for OAuth callback
        print("[7] Waiting for OAuth callback...")
        oauth_code = None
        try:
            _callback_event.wait(timeout=60)
            oauth_code = _callback_code
        except:
            pass
        
        if not oauth_code:
            current_url = page.url
            if 'code=' in current_url:
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                oauth_code = params.get('code', [None])[0]
        
        if oauth_code:
            print(f"    OAuth code captured!")
            account_info['oauth_code'] = oauth_code
            account_info['code_verifier'] = code_verifier
            account_info['status'] = 'success'
            
            # Exchange code for token (through proxy)
            print("[8] Exchanging code for token...")
            try:
                token_data = json.dumps({
                    'grant_type': 'authorization_code',
                    'client_id': client_id,
                    'code': oauth_code,
                    'redirect_uri': f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback',
                    'code_verifier': code_verifier
                })
                status, body = forward_proxy_request('POST', 'https://oidc.us-east-1.amazonaws.com/token', 
                                                       headers={'Content-Type': 'application/json'}, data=token_data)
                if status == 200:
                    token_resp = json.loads(body)
                    account_info['access_token'] = token_resp.get('access_token', '')
                    account_info['refresh_token'] = token_resp.get('refresh_token', '')
                    account_info['id_token'] = token_resp.get('id_token', '')
                    print(f"    Token captured!")
                else:
                    print(f"    [!] Token exchange failed: {status}")
                    account_info['status'] = 'partial'
            except Exception as e:
                print(f"    [!] Token error: {e}")
                account_info['status'] = 'partial'
        else:
            print("    [!] No OAuth code")
            account_info['status'] = 'no_token'
        
        print(f"\n    Final URL: {page.url[:100]}")
        print(f"    API calls: {len(api_responses)}")
        for r in api_responses:
            print(f"      step={r['step']}, status={r['status']}")
        
        page.screenshot(path='/home/ubuntu/kiro-gen/final_state.png')
        browser.close()
    
    callback_server.shutdown()
    return account_info


if __name__ == '__main__':
    result = create_account()
    print(f"\n{'='*60}")
    print(f"Result: {json.dumps(result, indent=2, default=str)}")
    print(f"{'='*60}")
    
    with open('/home/ubuntu/kiro-gen/last_account.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)
