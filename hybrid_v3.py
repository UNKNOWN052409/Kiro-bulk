"""
Kiro AI Account Creator - Hybrid V4
Browser WITHOUT proxy for fast SPA loading.
Intercepts API calls via page.route() and replays them through residential SOCKS5 proxy.
Returns proxied responses to the browser.
Uses curl_cffi with SOCKS5 proxy directly (no HTTP wrapper needed).
"""

import uuid, secrets, hashlib, base64, requests, json, time, socket, threading, http.server, random, subprocess
import socks  # PySocks for persistent SOCKS5 connection
from socks5_session import Socks5Session
from urllib.parse import quote, urlparse, parse_qs
from playwright.sync_api import sync_playwright

# Config
REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"]
CALLBACK_PORT = 9997
DIRECTORY_ID = 'd-9067642ac7'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

# ProxyRise config - SOCKS5 direct
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_SESSION_ID = 'res-us'

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'Mia', 'James', 'Charlotte', 'Benjamin', 'Amelia', 'Lucas', 'Harper', 'Henry', 'Evelyn', 'Alexander',
               'Sebastian', 'Jack', 'Owen', 'Theodore', 'Aria', 'Scarlett', 'Victoria', 'Madison', 'Luna', 'Grace']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
              'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson',
              'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker', 'Young', 'Allen', 'King', 'Wright', 'Scott']


def extract_otp():
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
        print(f"    Gmail error: {e}")
        return None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    captured_code = None
    captured_state = None
    
    def do_GET(self):
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


def check_proxy():
    """Check if SOCKS5 proxy is working using curl."""
    result = subprocess.run(
        ['curl', '-x', SOCKS5_URL, '-s', '--max-time', '10',
         'https://api.ipquery.io/?format=json'],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode == 0 and result.stdout.strip():
        return json.loads(result.stdout)
    return None


# Global persistent SOCKS5 session
_persistent_session = None

def get_persistent_session():
    global _persistent_session
    if _persistent_session is None:
        _persistent_session = Socks5Session(
            host='gw.proxyrise.com',
            port=443,
            username='res-us',
            password=PROXYRISE_API_KEY
        )
    return _persistent_session


def replay_through_proxy(method, url, headers, body=None):
    """Replay a request through the persistent SOCKS5 session (same IP for all requests)."""
    try:
        # Remove headers that might cause issues
        clean_headers = dict(headers)
        for h in ['host', 'content-length', 'connection', 'accept-encoding']:
            clean_headers.pop(h, None)
        
        session = get_persistent_session()
        resp = session.request(
            method=method,
            url=url,
            headers=clean_headers,
            body=body,
            timeout=30
        )
        return resp
    except Exception as e:
        print(f"    [PROXY ERR] {url[:60]}: {type(e).__name__}: {str(e)[:100]}")
        return None


def main():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email = f'{random_suffix}@havenhaus.in'
    password = f'Kiro{random_suffix[:4]}!2026'
    
    print(f"Creating: {full_name} <{email}>")
    print(f"Password: {password}")
    print()
    
    # Verify proxy using persistent session
    print("[0] Verifying SOCKS5 proxy (persistent session)...")
    session = get_persistent_session()
    proxy_ip = session.get_ip()
    if proxy_ip:
        print(f"    Proxy IP: {proxy_ip} (consistent for all requests)")
    else:
        print("    [!] Proxy not working!")
        # Fallback to curl check
        ip_info = check_proxy()
        if ip_info:
            print(f"    Fallback Proxy IP: {ip_info['ip']} ({ip_info['isp']['isp']}, {ip_info['location']['city']})")
        else:
            print("    [!] Proxy completely not working!")
            return
    
    # Register OIDC client (direct)
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
    
    print("[2] Launching browser (NO proxy - fast SPA loading)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=UA,
            locale='en-US',
        )
        page = context.new_page()
        page.set_default_timeout(120000)
        page.set_default_navigation_timeout(120000)
        
        # Track API responses
        api_responses = []
        
        # Intercept API calls and replay through proxy
        def handle_route(route):
            request = route.request
            url = request.url
            
            # Only intercept API calls to AWS signin/profile domains
            if ('signin.aws' in url or 'profile.aws' in url) and '/api/execute' in url:
                print(f"    [ROUTE] {request.method} {url.split('?')[0]}")
                print(f"    [ROUTE] Body: {str(request.post_data)[:200]}")
                
                # Build headers for the replay
                headers = dict(request.headers)
                
                # Replay through proxy
                resp = replay_through_proxy(
                    method=request.method,
                    url=url,
                    headers=headers,
                    body=request.post_data
                )
                
                if resp:
                    api_responses.append({'url': url.split('?')[0].split('/')[-1], 'status': resp.status_code})
                    status_text = 'OK' if resp.status_code < 400 else 'ERR'
                    print(f"    [ROUTE {status_text}] status={resp.status_code}, body: {str(resp.text)[:150]}")
                    
                    if resp.status_code < 400:
                        try:
                            resp_headers = dict(resp.headers)
                            # Remove headers that cause issues
                            for h in ['transfer-encoding', 'connection', 'keep-alive']:
                                resp_headers.pop(h, None)
                            route.fulfill(
                                status=resp.status_code,
                                headers=resp_headers,
                                body=resp.content
                            )
                        except Exception as e:
                            print(f"    [ROUTE fulfill error] {e}")
                            route.fallback()
                    else:
                        # If proxy returns error, try to get error body
                        try:
                            route.fulfill(
                                status=resp.status_code,
                                headers={'content-type': 'application/json'},
                                body=resp.text
                            )
                        except:
                            route.fallback()
                else:
                    print(f"    [ROUTE FAILED] Falling back to direct")
                    route.fallback()
            else:
                route.fallback()
        
        page.route('**/*', handle_route)
        
        # Navigate to OIDC authorize (no proxy - fast)
        print("[3] Navigating to OIDC authorize (direct - fast)...")
        try:
            page.goto(auth_url, wait_until='domcontentloaded', timeout=60000)
            print("    Page loaded!")
        except Exception as e:
            print(f"    Navigation error: {e}")
            try:
                page.goto(auth_url, wait_until='commit', timeout=60000)
                print("    Page loaded (commit)!")
            except Exception as e2:
                print(f"    Second attempt failed: {e2}")
                browser.close()
                callback_server.shutdown()
                return
        
        # Wait for email form
        print("[4] Waiting for email form...")
        email_ready = False
        for i in range(15):
            time.sleep(1)
            try:
                body = page.evaluate('document.body.innerText')
                if 'email' in body.lower() and ('continue' in body.lower() or 'sign' in body.lower()):
                    print(f"    Form ready at {i}s")
                    email_ready = True
                    break
                elif 'err-837' in body.lower():
                    print(f"    [{i}s] ERR-837!")
                    break
            except:
                pass
        
        if email_ready:
            print("[5] Filling email...")
            try:
                email_input = page.locator('input[type="email"]').first
                email_input.fill(email)
                time.sleep(0.5)
                page.locator('button:has-text("Continue")').first.click()
                print("    Email submitted!")
            except Exception as e:
                print(f"    Email error: {e}")
        
        # Wait for redirect to profile.aws.amazon.com
        print("[6] Waiting for profile.aws.amazon.com redirect...")
        profile_reached = False
        try:
            page.wait_for_url('**profile.aws.amazon.com**', timeout=60000)
            profile_reached = True
            print("    Redirected to profile.aws.amazon.com!")
        except Exception as e:
            try:
                if 'profile.aws.amazon.com' in page.url:
                    profile_reached = True
            except:
                pass
        
        if not profile_reached:
            for i in range(12):
                time.sleep(5)
                try:
                    if 'profile.aws.amazon.com' in page.url:
                        profile_reached = True
                        print(f"    Profile reached at {i*5}s (fallback)!")
                        break
                except:
                    pass
        
        if profile_reached:
            # Wait for name page - should be fast since SPA loads directly
            print("[7] Waiting for name page...")
            name_ready = False
            for i in range(30):
                time.sleep(1)
                try:
                    body = page.evaluate('document.body.innerText')
                    if 'enter your name' in body.lower():
                        print(f"    Name page ready at {i}s!")
                        name_ready = True
                        break
                    elif 'err-837' in body.lower():
                        print(f"    [{i}s] ERR-837!")
                        break
                except:
                    pass
            
            if name_ready:
                # Dismiss cookie dialog
                try:
                    accept_btn = page.locator('button:has-text("Accept")').first
                    if accept_btn.is_visible(timeout=3000):
                        accept_btn.click()
                        time.sleep(1)
                except:
                    pass
                
                # Fill name
                print("[8] Filling name...")
                try:
                    name_input = page.locator('input[type="text"]').first
                    name_input.fill(full_name)
                    time.sleep(0.5)
                    page.locator('button:has-text("Continue")').first.click()
                    print(f"    Name filled: {full_name}!")
                except Exception as e:
                    print(f"    Name error: {e}")
                
                # Wait for OTP page
                print("[9] Waiting for OTP page...")
                otp_ready = False
                for i in range(30):
                    time.sleep(1)
                    try:
                        body = page.evaluate('document.body.innerText')
                        if 'code' in body.lower() and ('enter' in body.lower() or 'verification' in body.lower()):
                            print(f"    OTP page at {i}s!")
                            otp_ready = True
                            break
                        elif 'err-837' in body.lower():
                            print(f"    [{i}s] ERR-837!")
                            break
                    except:
                        pass
                
                if otp_ready:
                    print("[10] Fetching OTP...")
                    otp = None
                    for attempt in range(10):
                        otp = extract_otp()
                        if otp:
                            break
                        time.sleep(3)
                    
                    if otp:
                        print(f"    OTP: {otp}")
                        try:
                            otp_inputs = page.locator('input[type="text"]').all()
                            if not otp_inputs:
                                otp_inputs = page.locator('input:not([type])').all()
                            
                            if otp_inputs:
                                otp_inputs[0].fill(otp)
                                time.sleep(0.5)
                                page.locator('button:has-text("Continue")').first.click()
                                print("    OTP submitted!")
                                
                                # Wait for password page
                                print("[11] Waiting for password page...")
                                time.sleep(3)
                                
                                # Set password
                                try:
                                    pw_inputs = page.locator('input[type="password"]').all()
                                    if len(pw_inputs) >= 1:
                                        pw_inputs[0].fill(password)
                                        if len(pw_inputs) >= 2:
                                            pw_inputs[1].fill(password)
                                        time.sleep(0.5)
                                        
                                        btn = page.locator('button:has-text("Create account")').first
                                        if not btn.is_visible(timeout=2000):
                                            btn = page.locator('button:has-text("Continue")').first
                                        btn.click()
                                        print("    Password submitted!")
                                        
                                        # Wait for token
                                        print("[12] Waiting for token...")
                                        time.sleep(5)
                                        for i in range(10):
                                            time.sleep(2)
                                            if CallbackHandler.captured_code:
                                                print(f"    Auth code: {CallbackHandler.captured_code}")
                                                break
                                            if 'code=' in page.url:
                                                parsed = urlparse(page.url)
                                                params = parse_qs(parsed.query)
                                                code = params.get('code', [None])[0]
                                                print(f"    Auth code: {code}")
                                                CallbackHandler.captured_code = code
                                                break
                                except Exception as e:
                                    print(f"    Password error: {e}")
                        except Exception as e:
                            print(f"    OTP error: {e}")
                    else:
                        print("    No OTP!")
        
        # Final state
        print("\n[FINAL]")
        try:
            body = page.evaluate('document.body.innerText')
            url = page.url
            print(f"    URL: {url}")
            print(f"    Body: {body[:300]}")
        except:
            pass
        
        try:
            page.screenshot(path='/home/ubuntu/kiro-gen/final_state.png', timeout=5000)
        except:
            pass
        
        browser.close()
    
    callback_server.shutdown()
    
    result = {
        'email': email,
        'password': password,
        'name': full_name,
        'api_responses': api_responses,
    }
    with open('/home/ubuntu/kiro-gen/last_result.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\nDone. API responses: {len(api_responses)}")


if __name__ == '__main__':
    main()
