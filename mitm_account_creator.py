"""
Kiro Account Creator - Browser-based with residential proxy for ENTIRE session
All browser traffic goes through a local HTTP proxy that forwards to ProxyRise SOCKS5.
This ensures consistent residential IP for all requests (SPA load + API calls).
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
import threading, imaplib, subprocess, socket
from urllib.parse import quote, urlparse

# ==================== CONFIG ====================
REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]
CALLBACK_PORT = 9997
LOCAL_PROXY_PORT = 8899

# ProxyRise SOCKS5 proxy with sticky session
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_SESSION_ID = str(random.randint(10000, 999999999))
SOCKS5_PROXY_URL = f'socks5://res-us-sid-{PROXY_SESSION_ID}:{PROXYRISE_API_KEY}@gw.proxyrise.com:443'

# Gmail
GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_APP_PASSWORD = 'hlcveobitfwh terw'.replace(' ', '')

# Names
FIRST_NAMES = ["Aditya", "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Karan", "Deepika", "Arjun", 
               "Meera", "Rohan", "Kavya", "Nikhil", "Divya", "Siddharth", "Pooja", "Vishal", "Ritu", "Aman",
               "James", "Sarah", "Michael", "Emma", "David", "Olivia", "Daniel", "Sophia", "Matthew", "Isabella",
               "Christopher", "Mia", "Andrew", "Charlotte", "Joshua", "Amelia", "Ryan", "Harper", "Brandon", "Evelyn",
               "Aarav", "Vivaan", "Reyansh", "Krishna", "Ishaan", "Shaurya", "Atharv",
               "Liam", "Noah", "Ethan", "Mason", "Lucas", "Oliver", "Elijah", "William", "Benjamin"]
LAST_NAMES = ["Sharma", "Patel", "Singh", "Kumar", "Gupta", "Verma", "Mehta", "Agarwal", "Joshi", "Reddy",
              "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Anderson", "Taylor", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Moore", "Clark",
              "Nair", "Rao", "Pillai", "Menon", "Iyer", "Bhat", "Desai", "Shah", "Chopra",
              "Khanna", "Malhotra", "Thakur", "Jha", "Saxena", "Bansal"]

# ==================== HELPERS ====================

def generate_account():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{prefix}@havenhaus.in"
    chars = string.ascii_letters + string.digits + "!@#$%"
    length = random.randint(12, 16)
    password = ''.join(random.choices(chars, k=length))
    if not any(c.isupper() for c in password):
        password = password[:-1] + random.choice(string.ascii_uppercase)
    if not any(c.islower() for c in password):
        password = password[:-2] + random.choice(string.ascii_lowercase) + password[-1]
    if not any(c.isdigit() for c in password):
        password = password[:-3] + random.choice(string.digits) + password[-2:]
    if not any(not c.isalnum() for c in password):
        password = password[:-1] + random.choice("!@#$%")
    return first, last, email, password

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

def human_type(page, locator, text, min_delay=50, max_delay=150):
    """Type text with human-like delays"""
    for char in text:
        locator.type(char, delay=random.uniform(min_delay, max_delay))
        time.sleep(random.uniform(0.02, 0.1))

def start_local_proxy(session_id):
    """Start the local HTTP-to-SOCKS5 proxy wrapper"""
    proc = subprocess.Popen(
        ['python3', '/home/ubuntu/kiro-gen/proxy_wrapper.py', str(session_id)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for proxy to be ready
    for _ in range(10):
        try:
            s = socket.create_connection(('127.0.0.1', LOCAL_PROXY_PORT), timeout=1)
            s.close()
            return proc
        except:
            time.sleep(0.5)
    return proc

# ==================== TOKEN CALLBACK SERVER ====================
tokens_captured = {}

from http.server import HTTPServer, BaseHTTPRequestHandler

class TokenCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if '/oauth/callback' in self.path:
            parsed = urlparse(self.path)
            params = dict(p.split('=', 1) for p in parsed.query.split('&') if '=' in p)
            code = params.get('code', '')
            if code:
                tokens_captured['code'] = code
                tokens_captured['timestamp'] = time.time()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'OK')
                return
        self.send_response(404)
        self.end_headers()
    def log_message(self, format, *args):
        pass

# ==================== MAIN ACCOUNT CREATION ====================

def create_account():
    first_name, last_name, email_addr, password = generate_account()
    full_name = f"{first_name} {last_name}"
    
    result = {
        'first': first_name, 'last': last_name,
        'email': email_addr, 'password': password,
        'status': 'PENDING', 'error': None,
        'access_token': None, 'refresh_token': None, 'id_token': None,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }
    
    print(f"\n{'='*70}")
    print(f"Creating: {full_name} <{email_addr}>")
    print(f"Password: {password}")
    print(f"Proxy session: {PROXY_SESSION_ID}")
    print(f"{'='*70}")
    
    try:
        # Step 0: Register OIDC client (direct, no proxy needed)
        print("[0] Registering OIDC client...")
        reg_payload = {
            "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
            "clientType": "public",
            "scopes": GRANT_SCOPES,
            "grantTypes": ["authorization_code", "refresh_token"],
            "redirectUris": [f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"],
            "issuerUrl": ISSUER_URL
        }
        reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
        reg_resp.raise_for_status()
        client_id = reg_resp.json()['clientId']
        print(f"    Client ID: {client_id[:16]}...")
        
        # PKCE
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
        scopes_encoded = ' '.join(GRANT_SCOPES)
        state = secrets.token_urlsafe(16)
        redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
        auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                    f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
                    f'&state={state}&code_challenge={code_challenge}'
                    f'&code_challenge_method=S256')
        
        print(f"    Auth URL ready")
        
        # Start local proxy
        print("\n    Starting local proxy wrapper...")
        proxy_proc = start_local_proxy(PROXY_SESSION_ID)
        print(f"    Local proxy ready on port {LOCAL_PROXY_PORT}")
        
        # ==================== BROWSER: Full flow through residential proxy ====================
        print("\n[1-7] Browser flow starting (ALL through residential proxy)...")
        
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--disable-extensions',
                    '--window-size=1920,1080',
                ]
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                ignore_https_errors=True,
                proxy={
                    'server': f'http://127.0.0.1:{LOCAL_PROXY_PORT}',
                }
            )
            page = context.new_page()
            
            # Navigate to OIDC authorize URL
            print("    Navigating to OIDC authorize...")
            try:
                page.goto(auth_url, wait_until='domcontentloaded', timeout=120000)
            except Exception as e:
                print(f"    Nav: {type(e).__name__} (may be OK)")
            
            # Wait for the page to load and redirect
            print("    Waiting for redirect chain...")
            for i in range(60):
                time.sleep(2)
                url = page.url
                body_text = ''
                try:
                    body_text = page.evaluate('document.body.innerText')
                except:
                    pass
                
                if 'profile.aws.amazon.com' in url:
                    print(f"    Already on profile! [{i*2}s]")
                    break
                elif 'signin.aws' in url and 'workflowStateHandle' in url:
                    # Wait for the login form to actually render
                    has_form = False
                    try:
                        has_form = page.locator('input[type="email"], input[placeholder*="email" i], input[name="username"]').first.is_visible(timeout=3000)
                    except:
                        pass
                    if has_form:
                        print(f"    Login form visible [{i*2}s]")
                        print(f"    Page: {body_text[:80]}")
                        break
                    elif 'Get started' in body_text or ('Email' in body_text and 'Continue' in body_text):
                        print(f"    Page text visible [{i*2}s]: {body_text[:80]}")
                        break
                elif 'view.awsapps.com' in url:
                    pass  # Still redirecting
                else:
                    pass
                
                if i % 10 == 0 and i > 0:
                    print(f"    [{i*2}s] URL: {url[:60]}...")
            
            current_url = page.url
            print(f"    Current URL: {current_url[:100]}")
            
            # Check what page we're on
            body_text = ''
            try:
                body_text = page.evaluate('document.body.innerText')
            except:
                pass
            
            print(f"    Body: {body_text[:100]}")
            
            # Check if on signin page
            on_signin = False
            try:
                on_signin = page.locator('input[type="email"], input[placeholder*="email" i], input[name="username"]').first.is_visible(timeout=3000)
            except:
                pass
            if not on_signin:
                on_signin = 'Get started' in body_text or ('Email' in body_text and 'Continue' in body_text)
            
            if on_signin:
                print("\n    Filling email...")
                try:
                    email_input = page.locator('input[type="email"], input[placeholder*="email" i], input[name="username"]').first
                    if email_input and email_input.count() > 0 and email_input.is_visible():
                        human_type(page, email_input, email_addr)
                        print("    Email filled")
                        time.sleep(random.uniform(1, 2))
                        
                        val = email_input.input_value()
                        print(f"    Value: {val}")
                        
                        # Dismiss cookie dialogs
                        for dialog_text in ['Accept', 'Decline', 'Dismiss']:
                            try:
                                dialog_btn = page.locator(f'button:has-text("{dialog_text}")').first
                                if dialog_btn and dialog_btn.is_visible():
                                    dialog_btn.click()
                                    print(f"    Clicked '{dialog_text}' dialog")
                                    time.sleep(random.uniform(0.5, 1.5))
                            except:
                                pass
                        
                        # Click Continue
                        continue_btn = page.locator('button:has-text("Continue")').first
                        if continue_btn and continue_btn.is_visible():
                            print("    Clicking Continue...")
                            continue_btn.click()
                            time.sleep(random.uniform(3, 6))
                            body_after = page.evaluate('document.body.innerText')
                            print(f"    After: {body_after[:100]}")
                            print(f"    URL: {page.url[:80]}")
                        else:
                            print("    Continue NOT visible")
                except Exception as e:
                    print(f"    Email fill error: {e}")
                
                # Wait for profile page
                print("    Waiting for profile.aws.amazon.com...")
                for i in range(60):
                    time.sleep(2)
                    current_url = page.url
                    if 'profile.aws.amazon.com' in current_url:
                        print(f"    On profile page! [{i*2}s]")
                        break
                    if i % 10 == 0 and i > 0:
                        print(f"    [{i*2}s] URL: {current_url[:80]}")
            
            # ===== Handle profile.aws.amazon.com =====
            if 'profile.aws.amazon.com' in page.url:
                print("\n    Waiting for profile SPA to load...")
                for i in range(60):
                    time.sleep(2)
                    body_text = ''
                    try:
                        body_text = page.evaluate('document.body.innerText')
                    except:
                        pass
                    current_url = page.url
                    bt_lower = body_text.lower()
                    
                    # Check for various states
                    if 'err-837' in bt_lower:
                        print(f"    ERR-837 detected at [{i*2}s] - proxy not working!")
                        break
                    elif 'enter your name' in bt_lower or ('name' in bt_lower and 'email' in bt_lower):
                        print(f"    Name form visible [{i*2}s]: {body_text[:80]}")
                        break
                    elif 'verification code' in bt_lower or ('code' in bt_lower and 'verify' in bt_lower):
                        print(f"    OTP page visible [{i*2}s]: {body_text[:80]}")
                        break
                    elif 'password' in bt_lower and ('create' in bt_lower or 'confirm' in bt_lower):
                        print(f"    Password form visible [{i*2}s]: {body_text[:80]}")
                        break
                    elif 'oh no' in bt_lower or 'timed out' in bt_lower:
                        print(f"    Session error at [{i*2}s]: {body_text[:80]}")
                        break
                    elif body_text and len(body_text) > 30 and 'Privacy' not in body_text[:15]:
                        print(f"    Page content [{i*2}s]: {body_text[:100]}")
                        break
                    
                    if i % 10 == 0 and i > 0:
                        print(f"    [{i*2}s] URL: {current_url[:80]}, waiting...")
                
                # ===== STEP 5: Fill name =====
                print("\n    === Step 5: Fill name ===")
                time.sleep(random.uniform(1, 3))
                
                body_text = ''
                try:
                    body_text = page.evaluate('document.body.innerText')
                except:
                    pass
                
                if 'Enter your name' in body_text or ('Name' in body_text and 'Email' in body_text):
                    print("    Name form detected")
                    try:
                        name_input = page.locator('input[type="text"]').first
                        if name_input and name_input.is_visible():
                            name_input.click()
                            time.sleep(random.uniform(0.5, 1))
                            human_type(page, name_input, full_name)
                            print("    Name filled")
                            time.sleep(random.uniform(1, 2))
                            
                            # Press Enter to submit
                            name_input.press('Enter')
                            print("    Enter pressed")
                            time.sleep(random.uniform(3, 6))
                            
                            # Check result
                            body_after = page.evaluate('document.body.innerText')
                            print(f"    After name submit: {body_after[:150]}")
                    except Exception as e:
                        print(f"    Name fill error: {e}")
                
                # ===== STEP 6: OTP =====
                print("\n    === Step 6: OTP ===")
                otp_done = False
                for i in range(30):
                    time.sleep(2)
                    body_text = ''
                    try:
                        body_text = page.evaluate('document.body.innerText')
                    except:
                        pass
                    bt_lower = body_text.lower()
                    if 'verification code' in bt_lower or ('code' in bt_lower and 'verify' in bt_lower and 'enter' in bt_lower):
                        print(f"    OTP page detected [{i*2}s]")
                        
                        # Get OTP from Gmail
                        print("    Getting OTP from Gmail...")
                        otp = get_otp_from_gmail(email_addr, timeout=90)
                        if otp:
                            print(f"    OTP: {otp}")
                            time.sleep(random.uniform(1, 2))
                            try:
                                otp_input = page.locator('input[type="text"], input[name="otp"], input[placeholder*="code" i], input[placeholder*="OTP" i], input[maxlength="6"]').first
                                if otp_input and otp_input.is_visible():
                                    human_type(page, otp_input, otp, min_delay=80, max_delay=200)
                                    print("    OTP filled")
                                    time.sleep(random.uniform(1, 2))
                                    verify_btn = page.locator('button:has-text("Verify"), button:has-text("Continue"), button[type="submit"]').first
                                    if verify_btn.is_visible():
                                        verify_btn.click()
                                        print("    OTP submitted")
                                        otp_done = True
                                        time.sleep(random.uniform(3, 5))
                                    else:
                                        # Try Enter
                                        otp_input.press('Enter')
                                        print("    OTP submitted via Enter")
                                        otp_done = True
                                        time.sleep(random.uniform(3, 5))
                            except Exception as e:
                                print(f"    OTP error: {e}")
                        else:
                            print("    No OTP found in Gmail!")
                        break
                
                if not otp_done:
                    body_text = ''
                    try:
                        body_text = page.evaluate('document.body.innerText')
                    except:
                        pass
                    print(f"    OTP page not reached. State: {body_text[:150]}")
                
                # ===== STEP 7: Password =====
                print("\n    === Step 7: Password ===")
                time.sleep(random.uniform(2, 4))
                
                body_text = ''
                try:
                    body_text = page.evaluate('document.body.innerText')
                except:
                    pass
                
                bt_lower = body_text.lower()
                if 'password' in bt_lower and ('create' in bt_lower or 'enter' in bt_lower or 'confirm' in bt_lower):
                    print("    Password form detected")
                    try:
                        pw_inputs = page.locator('input[type="password"]')
                        count = pw_inputs.count()
                        print(f"    Password inputs: {count}")
                        if count >= 1:
                            # Fill first password input
                            pw_input = pw_inputs.first
                            pw_input.click()
                            time.sleep(random.uniform(0.5, 1))
                            human_type(page, pw_input, password, min_delay=30, max_delay=100)
                            print("    Password filled")
                            
                            # Fill confirm password if exists
                            if count >= 2:
                                pw_confirm = pw_inputs.nth(1)
                                pw_confirm.click()
                                time.sleep(random.uniform(0.5, 1))
                                human_type(page, pw_confirm, password, min_delay=30, max_delay=100)
                                print("    Confirm password filled")
                            
                            time.sleep(random.uniform(1, 2))
                            
                            # Click Create/Submit
                            create_btn = page.locator('button:has-text("Create"), button:has-text("Submit"), button[type="submit"]').first
                            if create_btn and create_btn.is_visible():
                                create_btn.click()
                                print("    Password submitted")
                                time.sleep(random.uniform(3, 6))
                            else:
                                pw_input.press('Enter')
                                print("    Password submitted via Enter")
                                time.sleep(random.uniform(3, 6))
                    except Exception as e:
                        print(f"    Password error: {e}")
                else:
                    print(f"    Password form not detected. State: {body_text[:150]}")
                
                # Final state check
                time.sleep(random.uniform(2, 4))
                body_text = ''
                try:
                    body_text = page.evaluate('document.body.innerText')
                except:
                    pass
                print(f"    Final state: {body_text[:150]}")
                print(f"    Final URL: {page.url[:100]}")
            
            # Wait for token callback
            print("\n    Waiting for token callback...")
            token_received = False
            for i in range(30):
                if 'code' in tokens_captured:
                    print(f"    TOKEN CAPTURED! Code: {tokens_captured['code'][:30]}...")
                    result['status'] = 'SUCCESS'
                    result['authorization_code'] = tokens_captured['code']
                    token_received = True
                    break
                if i % 5 == 0:
                    body_text = ''
                    try:
                        body_text = page.evaluate('document.body.innerText')
                    except:
                        pass
                    print(f"    [{i*2}s] URL: {page.url[:50]}, Body: {body_text[:50]}")
                time.sleep(2)
            
            if not token_received:
                print("    No token received within timeout")
            
            browser.close()
        
        # Kill proxy
        if proxy_proc:
            proxy_proc.terminate()
        
        if result['status'] != 'SUCCESS':
            result['status'] = 'PARTIAL'
        
    except Exception as e:
        result['status'] = 'FAILED'
        result['error'] = str(e)
        print(f"\n    FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    return result


if __name__ == '__main__':
    print("\n" + "="*70)
    print("Kiro Account Creator - Full Browser Flow (Residential Proxy)")
    print("="*70)
    
    # Start token callback server
    token_server = HTTPServer(('127.0.0.1', CALLBACK_PORT), TokenCallbackHandler)
    token_thread = threading.Thread(target=token_server.serve_forever, daemon=True)
    token_thread.start()
    print(f"Token callback server on port {CALLBACK_PORT}")
    
    # Create account
    result = create_account()
    
    print(f"\n{'='*70}")
    print(f"Final Status: {result['status']}")
    if result.get('error'):
        print(f"Error: {result['error']}")
    print(f"{'='*70}")
    
    # Save
    tokens_file = '/home/ubuntu/kiro-gen/captured_tokens.json'
    try:
        with open(tokens_file, 'r') as f:
            existing = json.load(f)
    except:
        existing = []
    existing.append(result)
    with open(tokens_file, 'w') as f:
        json.dump(existing, f, indent=2)
    
    success = sum(1 for r in existing if r.get('status') == 'SUCCESS')
    partial = sum(1 for r in existing if r.get('status') == 'PARTIAL')
    print(f"\nTotal: {len(existing)}, Success: {success}, Partial: {partial}")
