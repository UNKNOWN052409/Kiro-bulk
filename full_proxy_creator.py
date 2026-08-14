"""
Kiro AI Account Creator - Full Proxy V5
Uses residential proxy for the ENTIRE browser session.
Detects state based on API responses (not innerText polling).
Very long timeouts to account for slow residential proxy.
"""

import uuid, secrets, hashlib, base64, requests, json, time, socket, threading, http.server, random, subprocess
from urllib.parse import quote, urlparse, parse_qs
from playwright.sync_api import sync_playwright

# Config
REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"]
CALLBACK_PORT = 9997
LOCAL_PROXY_PORT = 8899
DIRECTORY_ID = 'd-9067642ac7'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

# ProxyRise config
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


def start_proxy():
    """Start proxy wrapper as a separate process."""
    proc = subprocess.Popen(
        ['python3', '-u', '/home/ubuntu/kiro-gen/proxy_wrapper_standalone.py', 
         '--port', str(LOCAL_PROXY_PORT),
         '--session', PROXY_SESSION_ID],
        stdout=open('/home/ubuntu/kiro-gen/proxy_wrapper.log', 'w'),
        stderr=subprocess.STDOUT,
        cwd='/home/ubuntu/kiro-gen',
        env={**__import__('os').environ, 'PYTHONUNBUFFERED': '1'}
    )
    # Wait for proxy to be ready
    for i in range(10):
        time.sleep(0.5)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', LOCAL_PROXY_PORT))
            sock.close()
            if result == 0:
                return proc
        except:
            pass
    return proc


def check_proxy():
    """Check if proxy is working."""
    result = subprocess.run(
        ['curl', '-x', f'http://127.0.0.1:{LOCAL_PROXY_PORT}', '-s', '--max-time', '15',
         'https://api.ipquery.io/?format=json'],
        capture_output=True, text=True, timeout=20
    )
    if result.returncode == 0 and result.stdout.strip():
        return json.loads(result.stdout)
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
    print(f"Proxy session: {PROXY_SESSION_ID}")
    print()
    
    # STEP 0: Start proxy wrapper FIRST
    print(f"[0] Starting local proxy on :{LOCAL_PROXY_PORT}...")
    proxy_proc = start_proxy()
    time.sleep(2)
    
    # Verify proxy
    print("[1] Verifying proxy...")
    ip_info = check_proxy()
    if ip_info:
        print(f"    Proxy IP: {ip_info['ip']} ({ip_info['isp']['isp']}, {ip_info['location']['city']})")
    else:
        print("    [!] Proxy not working!")
        return
    
    # Register OIDC client (direct connection - no proxy needed)
    print("[2] Registering OIDC client...")
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
    
    print("[3] Launching browser (full proxy)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                f'--proxy-server=http://127.0.0.1:{LOCAL_PROXY_PORT}',
                '--ignore-certificate-errors',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=UA,
            locale='en-US',
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(900000)  # 15 min
        page.set_default_navigation_timeout(900000)
        
        # Track API state machine
        api_steps = []
        current_step = None
        
        def on_response(response):
            nonlocal current_step
            url = response.url
            if '/api/execute' in url:
                try:
                    body = response.json()
                    step = body.get('stepId', '')
                    error = body.get('message', {}).get('errorCode', '')
                    api_steps.append({'step': step, 'error': error, 'time': time.time()})
                    if step:
                        current_step = step
                        print(f"    [API] step={step}" + (f" ERR={error}" if error else ""))
                except:
                    pass
        
        page.on('response', on_response)
        
        # Navigate to OIDC authorize
        print("[4] Navigating to OIDC authorize...")
        try:
            page.goto(auth_url, wait_until='commit', timeout=600000)
            print("    Page loaded (commit)!")
        except Exception as e:
            print(f"    Navigation error: {e}")
            browser.close()
            callback_server.shutdown()
            proxy_proc.kill()
            return
        
        # STATE MACHINE:
        # "" -> start -> get-identity-user -> [fill email] -> user-signup -> start -> get-verified-username -> [fill name] -> send-otp -> [fill OTP] -> password -> [create account] -> token
        
        # Wait for get-identity-user step (email form)
        print("[5] Waiting for email form (step=get-identity-user)...")
        email_step_reached = False
        for i in range(300):  # 10 min
            time.sleep(2)
            if current_step == 'get-identity-user':
                email_step_reached = True
                print(f"    Email form ready at {i*2}s!")
                break
            # Check for errors
            if any(s.get('error') and 'ERR-837' in str(s.get('error')) for s in api_steps):
                print(f"    [{i*2}s] ERR-837 detected in API response!")
                break
        
        if email_step_reached:
            # Wait for the DOM to render the email input
            print("[6] Waiting for email input to render...")
            email_input_ready = False
            for i in range(120):  # 4 min
                time.sleep(2)
                try:
                    result = page.evaluate("""
                        () => {
                            const inputs = document.querySelectorAll('input');
                            for (const input of inputs) {
                                if (input.type === 'email') {
                                    return {found: true, visible: input.offsetParent !== null};
                                }
                            }
                            return {found: false, visible: false};
                        }
                    """)
                    if result.get('found'):
                        email_input_ready = True
                        print(f"    Email input found at {i*2}s!")
                        break
                except:
                    pass
            
            if email_input_ready:
                # Fill email
                print("[7] Filling email...")
                try:
                    page.evaluate(f"""
                        () => {{
                            const inputs = document.querySelectorAll('input');
                            for (const input of inputs) {{
                                if (input.type === 'email' && input.offsetParent !== null) {{
                                    input.focus();
                                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    setter.call(input, '{email}');
                                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }}
                            }}
                            return false;
                        }}
                    """)
                    time.sleep(1)
                    # Click Continue
                    page.evaluate("""
                        () => {
                            const buttons = document.querySelectorAll('button');
                            for (const btn of buttons) {
                                const text = btn.textContent.trim().toLowerCase();
                                if (text === 'continue') {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    print("    Email submitted!")
                except Exception as e:
                    print(f"    Email error: {e}")
        
        # Wait for user-signup step (redirect to profile.aws.amazon.com)
        print("[8] Waiting for user-signup step (redirect)...")
        signup_step_reached = False
        for i in range(300):  # 10 min
            time.sleep(2)
            if current_step == 'start' and 'user-signup' in str(api_steps):
                signup_step_reached = True
                print(f"    Signup redirect at {i*2}s!")
                break
            if 'profile.aws.amazon.com' in page.url:
                signup_step_reached = True
                print(f"    Profile URL detected at {i*2}s!")
                break
        
        if not signup_step_reached:
            # Check URL as fallback
            for i in range(60):
                time.sleep(5)
                if 'profile.aws.amazon.com' in page.url:
                    signup_step_reached = True
                    print(f"    Profile URL detected (fallback) at {i*5}s!")
                    break
        
        if signup_step_reached:
            # Wait for get-verified-username step (name form)
            print("[9] Waiting for name form (step=get-verified-username)...")
            name_step_reached = False
            for i in range(300):  # 10 min
                time.sleep(2)
                if current_step == 'get-verified-username':
                    name_step_reached = True
                    print(f"    Name form ready at {i*2}s!")
                    break
        
        if name_step_reached:
            # Wait for name input to render
            print("[10] Waiting for name input to render...")
            name_input_ready = False
            for i in range(120):
                time.sleep(2)
                try:
                    result = page.evaluate("""
                        () => {
                            const inputs = document.querySelectorAll('input');
                            for (const input of inputs) {
                                if ((input.type === 'text' || !input.type) && input.offsetParent !== null) {
                                    return {found: true};
                                }
                            }
                            // Also check for any visible input
                            for (const input of inputs) {
                                if (input.offsetParent !== null) {
                                    return {found: true, type: input.type};
                                }
                            }
                            return {found: false};
                        }
                    """)
                    if result.get('found'):
                        name_input_ready = True
                        print(f"    Name input found at {i*2}s!")
                        break
                except:
                    pass
            
            if name_input_ready:
                # Dismiss cookie dialog
                try:
                    page.evaluate("""
                        () => {
                            const buttons = document.querySelectorAll('button');
                            for (const btn of buttons) {
                                if (btn.textContent.trim().toLowerCase().includes('accept')) {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    time.sleep(1)
                except:
                    pass
                
                # Fill name
                print("[11] Filling name...")
                try:
                    page.evaluate(f"""
                        () => {{
                            const inputs = document.querySelectorAll('input');
                            for (const input of inputs) {{
                                if ((input.type === 'text' || !input.type) && input.offsetParent !== null) {{
                                    input.focus();
                                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    setter.call(input, '{full_name}');
                                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }}
                            }}
                            return false;
                        }}
                    """)
                    time.sleep(1)
                    page.evaluate("""
                        () => {
                            const buttons = document.querySelectorAll('button');
                            for (const btn of buttons) {
                                const text = btn.textContent.trim().toLowerCase();
                                if (text === 'continue') {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    print(f"    Name filled: {full_name}!")
                except Exception as e:
                    print(f"    Name error: {e}")
                
                # Wait for send-otp step
                print("[12] Waiting for OTP form (step=send-otp)...")
                otp_step_reached = False
                for i in range(120):
                    time.sleep(2)
                    if current_step == 'send-otp':
                        otp_step_reached = True
                        print(f"    OTP form ready at {i*2}s!")
                        break
                
                if otp_step_reached:
                    # Get OTP from Gmail
                    print("[13] Fetching OTP from Gmail...")
                    otp = None
                    for attempt in range(15):
                        otp = extract_otp()
                        if otp:
                            break
                        time.sleep(5)
                    
                    if otp:
                        print(f"    OTP: {otp}")
                        # Wait for OTP input to render
                        time.sleep(3)
                        try:
                            page.evaluate(f"""
                                () => {{
                                    const inputs = document.querySelectorAll('input');
                                    for (const input of inputs) {{
                                        if ((input.type === 'text' || input.type === 'number' || !input.type) && input.offsetParent !== null) {{
                                            input.focus();
                                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                            setter.call(input, '{otp}');
                                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                            return true;
                                        }}
                                    }}
                                    return false;
                                }}
                            """)
                            time.sleep(1)
                            page.evaluate("""
                                () => {
                                    const buttons = document.querySelectorAll('button');
                                    for (const btn of buttons) {
                                        const text = btn.textContent.trim().toLowerCase();
                                        if (text === 'continue') {
                                            btn.click();
                                            return true;
                                        }
                                    }
                                    return false;
                                }
                            """)
                            print("    OTP submitted!")
                            
                            # Wait for password step
                            print("[14] Waiting for password form...")
                            for i in range(60):
                                time.sleep(2)
                                try:
                                    pw_inputs = page.evaluate("""
                                        () => document.querySelectorAll('input[type="password"]').length
                                    """)
                                    if pw_inputs >= 1:
                                        print(f"    Password form ready at {i*2}s!")
                                        break
                                except:
                                    pass
                            
                            # Set password
                            try:
                                page.evaluate(f"""
                                    () => {{
                                        const inputs = document.querySelectorAll('input[type="password"]');
                                        if (inputs.length >= 1) {{
                                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                            setter.call(inputs[0], '{password}');
                                            inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                                            inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                                            if (inputs.length >= 2) {{
                                                setter.call(inputs[1], '{password}');
                                                inputs[1].dispatchEvent(new Event('input', {{ bubbles: true }}));
                                                inputs[1].dispatchEvent(new Event('change', {{ bubbles: true }}));
                                            }}
                                            return true;
                                        }}
                                        return false;
                                    }}
                                """)
                                time.sleep(1)
                                page.evaluate("""
                                    () => {
                                        const buttons = document.querySelectorAll('button');
                                        for (const btn of buttons) {
                                            const text = btn.textContent.trim().toLowerCase();
                                            if (text === 'continue' || text === 'create account') {
                                                btn.click();
                                                return true;
                                            }
                                        }
                                        return false;
                                    }
                                """)
                                print("    Password submitted!")
                                
                                # Wait for token redirect
                                print("[15] Waiting for token redirect...")
                                time.sleep(5)
                                for i in range(15):
                                    time.sleep(2)
                                    if CallbackHandler.captured_code:
                                        print(f"    Auth code: {CallbackHandler.captured_code}")
                                        break
                                    if 'code=' in page.url:
                                        parsed = urlparse(page.url)
                                        params = parse_qs(parsed.query)
                                        code = params.get('code', [None])[0]
                                        print(f"    Auth code from URL: {code}")
                                        CallbackHandler.captured_code = code
                                        break
                            except Exception as e:
                                print(f"    Password error: {e}")
                        except Exception as e:
                            print(f"    OTP error: {e}")
                    else:
                        print("    No OTP received!")
        
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
    proxy_proc.kill()
    
    result = {
        'email': email,
        'password': password,
        'name': full_name,
        'proxy_session': PROXY_SESSION_ID,
        'api_steps': api_steps,
    }
    with open('/home/ubuntu/kiro-gen/last_result.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\nDone. API steps: {len(api_steps)}")


if __name__ == '__main__':
    main()
