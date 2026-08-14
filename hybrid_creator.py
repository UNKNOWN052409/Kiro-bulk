"""
Kiro Account Creator - Hybrid approach.
Browser WITHOUT proxy for SPA rendering (fast).
page.route() to intercept execute API calls and replay through residential proxy.
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time, socket
import imaplib, subprocess, signal, os, sys, threading, concurrent.futures
from urllib.parse import quote, parse_qs, urlparse
from playwright.sync_api import sync_playwright

# ==================== CONFIG ====================
REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]
CALLBACK_PORT = 9997
DIRECTORY_ID = 'd-9067642ac7'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

# ProxyRise
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXYRISE_SESSION = f'res-us-sid-{random.randint(100000000, 999999999)}'
GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_APP_PASSWORD = 'hlcveobitfwh' + 'terw'

# Names
FIRST_NAMES = ["Aditya", "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Karan", "Deepika", "Arjun", 
               "James", "Sarah", "Michael", "Emma", "David", "Olivia", "Daniel", "Sophia", "Matthew", "Isabella",
               "Christopher", "Mia", "Andrew", "Charlotte", "Joshua", "Amelia", "Ryan", "Harper", "Brandon", "Evelyn",
               "Nathan", "Lily", "Ethan", "Grace", "Lucas", "Chloe", "Mason", "Zoe", "Logan", "Aria"]
LAST_NAMES = ["Sharma", "Patel", "Singh", "Kumar", "Gupta", "Verma", "Smith", "Johnson", "Williams", "Brown",
              "Jones", "Garcia", "Miller", "Davis", "Anderson", "Taylor", "Thomas", "Jackson", "White", "Harris",
              "Wilson", "Moore", "Martin", "Lee", "Clark", "Lewis", "Walker", "Hall", "Young", "Allen"]


def get_otp_from_gmail(email_addr, timeout=120):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            mail.select('inbox')
            status, messages = mail.search(None, f'(TO "{email_addr}")')
            if status == 'OK' and messages[0]:
                msg_ids = messages[0].split()
                for msg_id in reversed(msg_ids[-5:]):
                    status, msg_data = mail.fetch(msg_id, '(BODY.PEEK[])')
                    if status == 'OK':
                        raw = msg_data[0][1]
                        body = raw.decode('utf-8', errors='ignore')
                        otp_match = re.search(r'\b(\d{6})\b', body)
                        if otp_match:
                            mail.logout()
                            return otp_match.group(1)
            mail.logout()
        except Exception:
            pass
        time.sleep(3)
    return None


def create_account():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f'{prefix}@havenhaus.in'
    chars = string.ascii_letters + string.digits + '!@#$%'
    password = ''.join(random.choices(chars, k=random.randint(14, 18)))
    if not any(c.isupper() for c in password):
        password = password[:-1] + random.choice(string.ascii_uppercase)
    if not any(c.isdigit() for c in password):
        password = password[:-2] + random.choice(string.digits) + password[-1]
    if not any(not c.isalnum() for c in password):
        password = password[:-1] + random.choice('!@#$%')
    
    print(f"\n{'='*70}")
    print(f"Creating: {full_name} <{email}>")
    print(f"{'='*70}")
    
    # Register OIDC client (no proxy needed)
    print("\n[0] Registering OIDC client...")
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
    scopes_encoded = ' '.join(GRANT_SCOPES)
    state = secrets.token_urlsafe(16)
    redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
                f'&state={state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    # Start callback server
    captured_auth_code = None
    
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal captured_auth_code
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if 'code' in params:
                captured_auth_code = params['code'][0]
                print(f"\n    CALLBACK: Captured auth code: {captured_auth_code[:30]}...")
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>OK</h1></body></html>')
        def log_message(self, format, *args):
            pass
    
    HTTPServer.allow_reuse_address = True
    callback_server = HTTPServer(('127.0.0.1', CALLBACK_PORT), CallbackHandler)
    callback_thread = threading.Thread(target=callback_server.serve_forever, daemon=True)
    callback_thread.start()
    print(f"Callback server started on :{CALLBACK_PORT}")
    
    with sync_playwright() as p:
        # Launch browser WITHOUT proxy (SPA renders fast on datacenter IP)
        print("\n[1] Launching browser (no proxy)...")
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
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        page.set_default_navigation_timeout(60000)
        
        # Track execute API responses
        execute_responses = []
        name_step_wsh = None
        
        def handle_response(response):
            if '/api/execute' in response.url:
                try:
                    body = response.json()
                    execute_responses.append(body)
                    step = body.get('stepId', 'N/A')
                    err = body.get('message', {}).get('errorCode', '') if isinstance(body.get('message'), dict) else ''
                    wsh = body.get('workflowStateHandle', '')[:20]
                    print(f"    [API] stepId={step}, error={err}, WSH={wsh}")
                    if step == 'user-signup':
                        nonlocal name_step_wsh
                        name_step_wsh = body.get('workflowStateHandle')
                except:
                    execute_responses.append({'raw': True})
        
        page.on('response', handle_response)
        
        # Navigate to auth URL (no proxy - fast)
        print("\n[2] Navigating to OIDC authorize...")
        try:
            page.goto(auth_url, wait_until='domcontentloaded', timeout=60000)
            print(f"    Current URL: {page.url[:100]}")
        except Exception as e:
            print(f"    Nav error: {e}")
        
        # Wait for email form
        print("\n[3] Waiting for email form...")
        for i in range(30):
            time.sleep(1)
            try:
                body = page.evaluate('document.body.innerText')
                if 'email' in body.lower() and ('continue' in body.lower() or 'sign' in body.lower()):
                    print(f"    [{i}s] Form ready: {body[:50]}")
                    break
            except:
                pass
        
        # Fill email
        print("\n[4] Filling email...")
        try:
            email_input = page.locator('input[type="email"]').first
            email_input.fill(email)
            time.sleep(0.5)
            continue_btn = page.locator('button:has-text("Continue")').first
            continue_btn.click()
            print("    Email submitted")
        except Exception as e:
            print(f"    Email error: {e}")
        
        # Wait for name step - the SPA navigates to a new page after email submit
        # This page should load fast since it's the same datacenter IP
        print("\n[5] Waiting for name step...")
        name_filled = False
        for i in range(30):
            time.sleep(2)
            try:
                # Check if we have inputs via JS
                input_info = page.evaluate("""
                    () => {
                        const results = [];
                        function collectInputs(root) {
                            root.querySelectorAll('input').forEach(inp => {
                                const style = window.getComputedStyle(inp);
                                const visible = style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                                results.push({
                                    type: inp.type || 'text',
                                    placeholder: inp.placeholder || '',
                                    ariaLabel: inp.getAttribute('aria-label') || '',
                                    name: inp.getAttribute('name') || '',
                                    visible: visible,
                                });
                            });
                            root.querySelectorAll('*').forEach(el => {
                                if (el.shadowRoot) {
                                    el.shadowRoot.querySelectorAll('input').forEach(inp => {
                                        results.push({
                                            type: inp.type || 'text',
                                            placeholder: inp.placeholder || '',
                                            ariaLabel: inp.getAttribute('aria-label') || '',
                                            name: inp.getAttribute('name') || '',
                                            visible: true,
                                        });
                                    });
                                }
                            });
                        }
                        collectInputs(document);
                        return JSON.stringify(results);
                    }
                """)
                
                inputs_data = json.loads(input_info) if input_info else []
                visible_inputs = [inp for inp in inputs_data if inp.get('visible')]
                
                if i % 5 == 0:
                    inp_summary = [f"{inp['type']}:{inp['placeholder'][:20]}" for inp in visible_inputs]
                    print(f"    [{i*2}s] Visible inputs: {inp_summary}")
                
                # Look for a name input (text type, not email/password)
                name_candidates = [inp for inp in visible_inputs 
                                   if inp.get('type', 'text') not in ('email', 'password', 'hidden', 'submit')]
                
                # Also check API responses for name step
                if execute_responses and not name_filled:
                    last = execute_responses[-1]
                    step = last.get('stepId', '')
                    if step == 'user-signup' and name_candidates:
                        print(f"    [{i*2}s] Name step detected via API + inputs found")
                        # Fill the name input
                        fill_result = page.evaluate(f"""
                            () => {{
                                const inputs = [];
                                function collectInputs(root) {{
                                    root.querySelectorAll('input').forEach(inp => {{
                                        if (inp.type !== 'hidden' && inp.type !== 'submit' && inp.type !== 'button') {{
                                            inputs.push(inp);
                                        }}
                                    }});
                                    root.querySelectorAll('*').forEach(el => {{
                                        if (el.shadowRoot) collectInputs(el.shadowRoot);
                                    }});
                                }}
                                collectInputs(document);
                                
                                // Find non-email, non-password input
                                let target = null;
                                for (const inp of inputs) {{
                                    if (inp.type !== 'email' && inp.type !== 'password') {{
                                        target = inp;
                                        break;
                                    }}
                                }}
                                
                                if (target) {{
                                    const name = '{full_name}';
                                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    setter.call(target, name);
                                    target.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    target.focus();
                                    target.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                                    target.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                                    return 'FILLED: ' + name;
                                }}
                                return 'NO_INPUT_FOUND';
                            }}
                        """)
                        print(f"    [{i*2}s] Name fill result: {fill_result}")
                        if 'FILLED' in fill_result:
                            name_filled = True
                            print("    Name submitted")
                            break
                
                # Also try by body text
                body = page.evaluate('document.body.innerText')
                bt = body.lower()
                if ('enter your name' in bt or 'your name' in bt) and name_candidates and not name_filled:
                    fill_result = page.evaluate(f"""
                        () => {{
                            const inputs = [];
                            function collectInputs(root) {{
                                root.querySelectorAll('input').forEach(inp => {{
                                    if (inp.type !== 'hidden' && inp.type !== 'submit' && inp.type !== 'button') {{
                                        inputs.push(inp);
                                    }}
                                }});
                                root.querySelectorAll('*').forEach(el => {{
                                    if (el.shadowRoot) collectInputs(el.shadowRoot);
                                }});
                            }}
                            collectInputs(document);
                            
                            let target = null;
                            for (const inp of inputs) {{
                                if (inp.type !== 'email' && inp.type !== 'password') {{
                                    target = inp;
                                    break;
                                }}
                            }}
                            
                            if (target) {{
                                const name = '{full_name}';
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                setter.call(target, name);
                                target.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                target.focus();
                                target.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                                target.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                                return 'FILLED: ' + name;
                            }}
                            return 'NO_INPUT_FOUND';
                        }}
                    """)
                    print(f"    [{i*2}s] Name fill result (body): {fill_result}")
                    if 'FILLED' in fill_result:
                        name_filled = True
                        print("    Name submitted (body)")
                        break
                        
            except Exception as e:
                if 'Execution context' in str(e):
                    if i % 5 == 0:
                        print(f"    [{i*2}s] Page still navigating...")
                else:
                    print(f"    [{i*2}s] Error: {e}")
        
        if not name_filled:
            print("    Name step timed out or not filled")
            # Continue anyway - maybe the name was submitted via API
        
        # Wait for OTP step
        print("\n[6] Waiting for OTP step...")
        otp_filled = False
        for i in range(45):
            time.sleep(2)
            try:
                body = page.evaluate('document.body.innerText')
                bt = body.lower()
                
                otp_detected = False
                if 'otp' in bt or ('code' in bt and ('enter' in bt or 'verification' in bt)) or 'enter the code' in bt:
                    otp_detected = True
                
                if otp_detected and not otp_filled:
                    print(f"    [{i*2}s] OTP step detected: {body[:50]}")
                    
                    # Get OTP from Gmail
                    print("    Getting OTP from Gmail...")
                    otp = get_otp_from_gmail(email)
                    if otp:
                        print(f"    OTP: {otp}")
                        # Fill OTP using JS (handles shadow DOM)
                        otp_result = page.evaluate(f"""
                            () => {{
                                const inputs = [];
                                function collectInputs(root) {{
                                    root.querySelectorAll('input').forEach(inp => {{
                                        if (inp.type !== 'hidden' && inp.type !== 'submit' && inp.type !== 'button') {{
                                            inputs.push(inp);
                                        }}
                                    }});
                                    root.querySelectorAll('*').forEach(el => {{
                                        if (el.shadowRoot) collectInputs(el.shadowRoot);
                                    }});
                                }}
                                collectInputs(document);
                                
                                // Find a text input (OTP)
                                let target = null;
                                for (const inp of inputs) {{
                                    if (inp.type === 'text' || inp.type === 'number' || inp.type === 'tel') {{
                                        target = inp;
                                        break;
                                    }}
                                }}
                                
                                if (target) {{
                                    const otp = '{otp}';
                                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    setter.call(target, otp);
                                    target.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    target.focus();
                                    target.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                                    target.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                                    return 'FILLED OTP: ' + otp;
                                }}
                                return 'NO_INPUT_FOUND';
                            }}
                        """)
                        print(f"    OTP result: {otp_result}")
                        if 'FILLED' in otp_result:
                            print("    OTP submitted")
                            otp_filled = True
                            break
                    else:
                        print("    No OTP found")
                        break
                elif i % 5 == 0:
                    print(f"    [{i*2}s] OTP waiting... body={body[:40]}")
            except:
                pass
        
        # Wait for password step
        print("\n[7] Waiting for password step...")
        pw_filled = False
        for i in range(30):
            time.sleep(2)
            try:
                body = page.evaluate('document.body.innerText')
                bt = body.lower()
                
                pw_detected = ('password' in bt and ('create' in bt or 'set' in bt or 'new' in bt))
                
                if pw_detected and not pw_filled:
                    print(f"    [{i*2}s] Password step detected: {body[:50]}")
                    pw_result = page.evaluate(f"""
                        () => {{
                            const inputs = [];
                            function collectInputs(root) {{
                                root.querySelectorAll('input').forEach(inp => {{
                                    if (inp.type !== 'hidden' && inp.type !== 'submit' && inp.type !== 'button') {{
                                        inputs.push(inp);
                                    }}
                                }});
                                root.querySelectorAll('*').forEach(el => {{
                                    if (el.shadowRoot) collectInputs(el.shadowRoot);
                                }});
                            }}
                            collectInputs(document);
                            
                            const pwInputs = inputs.filter(i => i.type === 'password');
                            const pw = '{password}';
                            
                            if (pwInputs.length > 0) {{
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                pwInputs.forEach((inp, idx) => {{
                                    setter.call(inp, pw);
                                    inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                }});
                                const last = pwInputs[pwInputs.length - 1];
                                last.focus();
                                last.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                                last.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
                                return 'FILLED PASSWORD (' + pwInputs.length + ' fields)';
                            }}
                            return 'NO_PASSWORD_INPUT';
                        }}
                    """)
                    print(f"    [{i*2}s] Password result: {pw_result}")
                    if 'FILLED' in pw_result:
                        print("    Password submitted")
                        pw_filled = True
                        break
                elif 'success' in bt or 'welcome' in bt or 'dashboard' in bt:
                    print(f"    [{i*2}s] Account created!")
                    pw_filled = True
                    break
                elif i % 5 == 0:
                    print(f"    [{i*2}s] PW waiting... body={body[:40]}")
            except:
                pass
        
        # Wait for token redirect
        print("\n[8] Waiting for token redirect...")
        for i in range(30):
            time.sleep(1)
            url = page.url
            if 'oauth/callback' in url:
                print(f"    [{i}s] Callback URL: {url[:120]}")
                code_match = re.search(r'code=([^&]+)', url)
                if code_match:
                    captured_auth_code = code_match.group(1)
                    print(f"    Auth code: {captured_auth_code[:30]}...")
                    break
            elif captured_auth_code:
                print(f"    [{i}s] Auth code captured via callback server")
                break
        
        if not captured_auth_code:
            print(f"    Final URL: {page.url[:120]}")
            print(f"    Title: {page.title()[:80]}")
            body = page.evaluate('document.body ? document.body.innerText : ""')
            print(f"    Body: {body[:200]}")
        
        storage = context.storage_state()
        browser.close()
    
    callback_server.shutdown()
    
    # Exchange code for tokens
    if captured_auth_code:
        print("\n[9] Exchanging code for tokens...")
        try:
            token_resp = requests.post(f'{OIDC_BASE}/token', data={
                'grant_type': 'authorization_code',
                'client_id': client_id,
                'code': captured_auth_code,
                'code_verifier': code_verifier,
                'redirect_uri': redirect_uri
            }, timeout=10)
            
            if token_resp.status_code == 200:
                token_data = token_resp.json()
                result = {
                    'email': email, 'name': full_name, 'password': password,
                    'access_token': token_data.get('access_token'),
                    'refresh_token': token_data.get('refresh_token'),
                    'id_token': token_data.get('id_token'),
                    'token_type': token_data.get('token_type'),
                    'expires_in': token_data.get('expires_in'),
                    'client_id': client_id,
                    'code_verifier': code_verifier,
                    'redirect_uri': redirect_uri,
                }
                
                accounts = []
                try:
                    with open('/home/ubuntu/kiro-gen/accounts.json', 'r') as f:
                        accounts = json.load(f)
                except:
                    pass
                accounts.append(result)
                with open('/home/ubuntu/kiro-gen/accounts.json', 'w') as f:
                    json.dump(accounts, f, indent=2)
                
                print(f"\n{'='*70}")
                print(f"SUCCESS!")
                print(f"  Email: {email}")
                print(f"  Password: {password}")
                print(f"  Access Token: {result['access_token'][:40]}...")
                print(f"  Refresh Token: {result['refresh_token'][:40]}...")
                print(f"{'='*70}")
                return result
            else:
                print(f"    Token exchange failed: {token_resp.text[:200]}")
        except Exception as e:
            print(f"    Token exchange error: {e}")
    
    return None


def main():
    print("=" * 70)
    print("Kiro AI Account Creator - Hybrid (No Proxy for SPA)")
    print("=" * 70)
    
    result = create_account()
    if not result:
        print("\nFAILED - account not created")
    else:
        print("\nDone!")


if __name__ == '__main__':
    main()
