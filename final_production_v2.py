"""
Final production v2 - Fixed timing and page detection.
Full verified flow: Email -> Name -> OTP -> Password -> Allow -> Token
"""
import sys, time, uuid, requests, secrets, hashlib, base64, threading, random, string
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

sys.path.insert(0, '/home/ubuntu/kiro-gen')
from extract_otp_v3 import extract_otp_gmail_v3

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
               "Krishna", "Ishaan", "Shaurya", "Atharv", "Advik", "Kabir", "Rudra",
               "Liam", "Noah", "Ethan", "Lucas", "Mason", "Logan", "Alexander", "James",
               "Benjamin", "William", "Henry", "Theodore", "Jack", "Leo", "Jackson"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Singh", "Patel", "Kumar", "Reddy", "Nair",
              "Iyer", "Chopra", "Malhotra", "Agarwal", "Joshi", "Mehta", "Rao",
              "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
              "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez"]

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

def generate_password():
    base = "TestPass" + str(random.randint(1000, 9999))
    special = random.choice("!@#$%")
    return base + special

def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def get_body(page):
    try:
        return page.evaluate("document.body ? document.body.innerText : ''")
    except:
        return ""

def wait_for_body(page, min_len=50, max_wait=600):
    """Wait for the page body to have meaningful content."""
    for i in range(max_wait // 2):
        time.sleep(2)
        body = get_body(page)
        if len(body) > min_len:
            return body
    return get_body(page)

def dismiss_cookies(page):
    try:
        for btn_text in ["Decline", "Dismiss", "Accept"]:
            btns = page.get_by_role("button", name=btn_text, exact=True).all()
            for btn in btns:
                try:
                    if btn.is_visible(timeout=500):
                        btn.click(timeout=1000)
                        time.sleep(1)
                except:
                    pass
    except:
        pass

def get_inputs(page, input_type=None):
    try:
        all_inputs = page.locator('input').all()
        visible = [inp for inp in all_inputs if inp.is_visible()]
        if input_type:
            visible = [inp for inp in visible if (inp.get_attribute('type') or 'text') == input_type]
        return visible
    except:
        return []

def click_button(page, btn_text, timeout=5000):
    for text in [btn_text]:
        try:
            btn = page.get_by_role("button", name=text).first
            if btn.is_visible(timeout=3000):
                btn.click(timeout=timeout)
                return True
        except:
            pass
    return False

def exchange_code_for_tokens(client_id, client_secret, code, code_verifier, redirect_uri):
    payload = {
        "clientId": client_id,
        "clientSecret": client_secret,
        "grantType": "authorization_code",
        "code": code,
        "codeVerifier": code_verifier,
        "redirectUri": redirect_uri
    }
    resp = requests.post(f'{OIDC_BASE}/token', json=payload, timeout=15)
    if resp.status_code == 200:
        return resp.json()
    return None

def create_account(email, name, password, port_start=8970):
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

    # Start callback server
    callback_port = port_start
    server = None
    while callback_port < port_start + 100:
        try:
            server = HTTPServer(('127.0.0.1', callback_port), Handler)
            break
        except OSError:
            callback_port += 1
    if server is None:
        return None, "No available port"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    redirect_uri = f'http://127.0.0.1:{callback_port}/oauth/callback'

    # Register OIDC client
    reg_payload = {
        "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
        "clientType": "public",
        "scopes": GRANT_SCOPES,
        "grantTypes": ["authorization_code", "refresh_token"],
        "redirectUris": [redirect_uri],
        "issuerUrl": ISSUER_URL
    }
    reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
    if reg_resp.status_code != 200:
        server.shutdown()
        return None, f"Register failed: {reg_resp.text[:200]}"
    reg_data = reg_resp.json()
    client_id = reg_data['clientId']
    client_secret = reg_data['clientSecret']

    # PKCE
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    scopes_encoded = ' '.join(GRANT_SCOPES)
    state = secrets.token_urlsafe(16)
    auth_url = f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scopes={scopes_encoded}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256'

    # Browser automation - launch with SOCKS5 proxy via Chrome args
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            proxy={'server': 'socks5://127.0.0.1:10800', 'bypass': '<-loopback>,*.amazonaws.com,*.awsapps.com,*.signin.aws,*.amazon.com,*.cloudfront.net,*.llnwd.net'},
            args=[
                '--no-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--window-size=1280,720',
            ],
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )

        # Close extra pages
        for pg in context.pages[1:]:
            try: pg.close()
            except: pass
        page = context.pages[0] if context.pages else context.new_page()

        # Navigate to auth URL
        try:
            page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
            time.sleep(2)
        except:
            pass
        
        try:
            page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        except:
            pass

        # Wait for render
        body = wait_for_body(page, max_wait=300)
        if len(body) < 50:
            # Page didn't render - navigate to about:blank and retry
            try:
                page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
                time.sleep(3)
                page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
            except:
                pass
            body = wait_for_body(page, max_wait=60)
        dismiss_cookies(page)
        body = wait_for_body(page, max_wait=30)

        print(f"    Initial body: {body[:100]}")

        # STATE MACHINE for the flow
        step = 'email'
        max_steps = 20
        step_count = 0

        while step_count < max_steps:
            step_count += 1
            body = get_body(page)
            body_lower = body.lower()
            url = page.url

            # Check if on Allow page
            if 'allow' in body_lower and 'access' in body_lower and 'kiro-' in body_lower:
                if click_button(page, "Allow access") or click_button(page, "Allow"):
                    print(f"    Allow clicked - exiting flow")
                    step = 'done'
                    break  # Exit the while loop

            # Check if on Email page
            if 'get started' in body_lower and 'email' in body_lower and 'continue' in body_lower:
                if step == 'email':
                    email_inputs = get_inputs(page, 'email')
                    if not email_inputs:
                        email_inputs = get_inputs(page, 'text')
                    if email_inputs:
                        print(f"    Filling email: {email}")
                        email_inputs[0].fill(email)
                        time.sleep(1)
                        click_button(page, "Continue")
                        print(f"    Email submitted, waiting for next page...")
                        # Wait LONGER for navigation (SPA takes time)
                        time.sleep(25)
                        body = wait_for_body(page, min_len=50, max_wait=300)
                        body_lower = body.lower()
                        print(f"    After email: {body[:80]}")
                        step = 'next'
                        continue

            # Check if on Name page
            if 'enter your name' in body_lower:
                if step in ('email', 'next'):
                    text_inputs = get_inputs(page, 'text')
                    if text_inputs:
                        print(f"    Filling name: {name}")
                        text_inputs[0].fill(name)
                        time.sleep(1)
                        click_button(page, "Continue")
                        print(f"    Name submitted, waiting for next page...")
                        time.sleep(25)
                        body = wait_for_body(page, min_len=50, max_wait=300)
                        body_lower = body.lower()
                        print(f"    After name: {body[:80]}")
                        step = 'otp'
                        continue

            # Check if on OTP page
            if 'verify your email' in body_lower or 'verification code' in body_lower or 'one-time' in body_lower:
                if step in ('next', 'otp'):
                    print(f"    OTP page detected")
                    otp = extract_otp_gmail_v3(email)
                    if otp:
                        print(f"    OTP: {otp}")
                        # Find the OTP input (6-digit)
                        text_inputs = get_inputs(page, 'text')
                        filled = False
                        for inp in text_inputs:
                            placeholder = inp.get_attribute('placeholder') or ''
                            if '6-digit' in placeholder or 'code' in placeholder.lower():
                                inp.fill(otp)
                                filled = True
                                break
                        if not filled and text_inputs:
                            text_inputs[-1].fill(otp)
                            filled = True
                        if filled:
                            time.sleep(2)
                            click_button(page, "Continue") or click_button(page, "Verify")
                            print(f"    OTP submitted, waiting for next page...")
                            time.sleep(25)
                            body = wait_for_body(page, min_len=50, max_wait=60)
                            body_lower = body.lower()
                            print(f"    After OTP: {body[:80]}")
                            step = 'password'
                            continue
                    else:
                        print(f"    [!] OTP extraction failed, retrying...")
                        time.sleep(10)
                        continue

            # Check if on Password page
            if 'create your password' in body_lower or ('password' in body_lower and 'confirm password' in body_lower):
                if step in ('otp', 'next', 'password'):
                    pw_inputs = get_inputs(page, 'password')
                    if pw_inputs:
                        print(f"    Filling password...")
                        pw_inputs[0].fill(password)
                        if len(pw_inputs) > 1:
                            pw_inputs[1].fill(password)
                        time.sleep(2)
                        click_button(page, "Continue")
                        print(f"    Password submitted, waiting for next page...")
                        time.sleep(25)
                        body = wait_for_body(page, min_len=50, max_wait=300)
                        body_lower = body.lower()
                        print(f"    After password: {body[:80]}")
                        step = 'allow'
                        continue

            # If we're on the same page for too long, check what we're seeing
            if step not in ('done', 'email') and step_count > 5:
                print(f"    [!] Stuck on step '{step}'. Body: {body[:100]}")
                time.sleep(5)
                body = wait_for_body(page, min_len=50, max_wait=30)
                body_lower = body.lower()

            # If body is empty and we're done, break
            if len(body) < 50 and step == 'done':
                print(f"    [!] Done - breaking")
                break
            # If body is empty, wait more (SPA through proxy can be slow)
            if len(body) < 50:
                print(f"    [!] Body empty, waiting more... URL: {url[:80]}")
                time.sleep(10)
                body = wait_for_body(page, min_len=50, max_wait=180)
                body_lower = body.lower()

        if step != 'done':
            body = get_body(page)
            return None, f"No Allow. Step: {step}. Body: {body[:200]}"

        # DON'T close page/context yet - browser needs to redirect to callback URL
        print(f"    Waiting for callback on port {callback_port}...")
        if not callback_event.wait(timeout=120):
            try:
                print(f"    Current URL: {page.url[:100]}")
            except:
                pass
            page.close()
            context.close()
            server.shutdown()
            return None, "Timeout waiting for auth code"
        print(f"    Callback received! Code: {auth_code_container['code'][:50]}...")
        try:
            page.close()
        except:
            pass
        try:
            context.close()
        except:
            pass
        try:
            browser.close()
        except:
            pass

    # Wait for callback
    if not callback_event.wait(timeout=120):
        server.shutdown()
        return None, "Timeout waiting for auth code"

    # Exchange code for tokens
    tokens = exchange_code_for_tokens(client_id, client_secret, auth_code_container['code'], code_verifier, redirect_uri)
    if tokens:
        result = {
            'email': email,
            'name': name,
            'password': password,
            'clientId': client_id,
            'clientSecret': client_secret,
            'accessToken': tokens.get('accessToken'),
            'refreshToken': tokens.get('refreshToken'),
            'idToken': tokens.get('idToken'),
            'expiresIn': tokens.get('expiresIn'),
        }
        server.shutdown()
        return result, None
    else:
        server.shutdown()
        return None, f"Token exchange failed. Code: {auth_code_container['code'][:50]}..."

if __name__ == '__main__':
    import json
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    start_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8970
    results = []

    print(f"[*] Creating {n} accounts...")
    for i in range(n):
        email = generate_email()
        name = generate_name()
        password = generate_password()
        print(f"[{i+1}/{n}] {email} ({name})")
        print(f"  Password: {password}")

        result, error = create_account(email, name, password, port_start=start_port + i)
        if result:
            results.append(result)
            print(f"  [OK] Token captured! Refresh: {result['refreshToken'][:50]}...")
            # Save immediately
            with open('captured_tokens.json', 'w') as f:
                json.dump(results, f, indent=2)
        else:
            print(f"  [!] Error: {error}")

        # Save progress
        with open('captured_tokens.json', 'w') as f:
            json.dump(results, f, indent=2)

    print(f"\n[*] Done! {len(results)}/{n} accounts created with tokens.")
