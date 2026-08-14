#!/usr/bin/env python3
"""
Hybrid approach:
- Steps 1-4: API-only through SOCKS5 proxy (verified working)
- Step 5: Use Playwright browser (with proxy) to load profile.aws.amazon.com SPA
- Steps 6+: API-only through proxy (using workflowState from SPA)
"""

import os, sys, time, json, random, string, uuid, re, threading, base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict

import requests
from requests.adapters import HTTPAdapter
import imaplib
import email as email_lib
from email.header import decode_header
from playwright.sync_api import sync_playwright

REGION = 'us-east-1'
CALLBACK_PORT = 9997

# ProxyRise SOCKS5 with sticky session
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_SESSION_ID = str(random.randint(10000, 999999999))
PROXY_URL = f'socks5://res-us-sid-{PROXY_SESSION_ID}:{PROXYRISE_API_KEY}@gw.proxyrise.com:443'

# Gmail
GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_APP_PASSWORD = 'hlcveobitfwh terw'.replace(' ', '')

# Names
FIRST_NAMES = ["Aarav", "Vihaan", "Aditya", "Sai", "Arjun", "Vivaan", "Krishna", "Ishaan", "Shaurya", "Atharva",
               "Priya", "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra", "Zara", "Fatima", "Ayesha",
               "Liam", "Noah", "Oliver", "Elijah", "James", "William", "Benjamin", "Lucas", "Henry", "Theodore",
               "Olivia", "Emma", "Charlotte", "Amelia", "Sophia", "Isabella", "Ava", "Mia", "Evelyn", "Luna",
               "Sophia", "Emma", "Olivia", "Ava", "Isabella", "Mia", "Charlotte", "Amelia", "Harper", "Evelyn",
               "James", "Oliver", "Harry", "Leo", "Jack", "Jacob", "Noah", "Ethan", "Charlie", "William",
               "Sophie", "Poppy", "Isla", "Grace", "Freya", "Evie", "Florence", "Willow", "Rosie", "Ivy"]

LAST_NAMES = ["Sharma", "Patel", "Singh", "Kumar", "Gupta", "Reddy", "Nair", "Iyer", "Rao", "Pillai",
              "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Mehta", "Joshi", "Desai", "Shah", "Thakur", "Chauhan", "Verma", "Agarwal", "Malhotra", "Kapoor",
              "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
              "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen"]


def generate_random_name():
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def generate_password():
    length = random.randint(12, 16)
    chars = string.ascii_letters + string.digits + "!@#$%"
    password = [random.choice(string.ascii_lowercase), random.choice(string.ascii_uppercase),
                random.choice(string.digits), random.choice("!@#$%")]
    password += [random.choice(chars) for _ in range(length - 4)]
    random.shuffle(password)
    return ''.join(password)


def generate_email():
    name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{name}@havenhaus.in"


# Token callback server
token_store = {}


class TokenCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if '/token' in self.path:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if 'token' in params:
                token = params['token'][0]
                token_store['refresh_token'] = token
                print(f"\n    *** TOKEN CAPTURED: {token[:50]}... ***")
            if 'code' in params:
                code = params['code'][0]
                token_store['auth_code'] = code
                print(f"\n    *** AUTH CODE CAPTURED: {code[:50]}... ***")
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, format, *args):
        pass


def get_otp_from_gmail(email_addr, timeout=60):
    """Get OTP from Gmail using IMAP."""
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select('inbox')

        start_time = time.time()
        while time.time() - start_time < timeout:
            status, messages = mail.search(None, 'UNSEEN')
            if status == 'OK':
                msg_ids = messages[0].split()
                for msg_id in reversed(msg_ids[-5:]):
                    status, msg_data = mail.fetch(msg_id, '(RFC822)')
                    if status == 'OK':
                        raw = msg_data[0][1]
                        msg = email_lib.message_from_bytes(raw)

                        # Check if it's from AWS
                        from_addr = msg.get('From', '')
                        if 'amazon' in from_addr.lower() or 'aws' in from_addr.lower():
                            for part in msg.walk():
                                if part.get_content_type() == 'text/plain':
                                    body = part.get_payload(decode=True)
                                    if body:
                                        body = body.decode('utf-8', errors='ignore')
                                        # Look for 6-digit code
                                        codes = re.findall(r'\b\d{6}\b', body)
                                        if codes:
                                            mail.logout()
                                            return codes[0]
            time.sleep(3)
        mail.logout()
    except Exception as e:
        print(f"    Gmail error: {e}")
    return None


def make_fingerprint():
    """Generate a fingerprint similar to the browser's ECdITeCs format."""
    # This is a simplified fingerprint - the real one is generated by the browser's JS
    # For API-only, we need to replicate it
    seed = f"{uuid.uuid4()}.{int(time.time() * 1000)}"
    fp_parts = [
        "ECdITeCs",
        base64.b64encode(os.urandom(256)).decode()[:320],
    ]
    return "ECdITeCs:" + fp_parts[1]


def make_profile_fingerprint():
    """Generate a fingerprint for the profile API calls."""
    return "ECdITeCs:" + base64.b64encode(os.urandom(4000)).decode()


def create_proxy_session():
    session = requests.Session()
    session.proxies = {'http': PROXY_URL, 'https': PROXY_URL}
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json;charset=UTF-8',
    })
    adapter = HTTPAdapter(max_retries=3)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def create_account():
    """Create a Kiro account using hybrid approach."""
    email_addr = generate_email()
    first, last = generate_random_name()
    full_name = f"{first} {last}"
    password = generate_password()

    result = {
        'email': email_addr,
        'name': full_name,
        'password': password,
        'status': 'PENDING',
    }

    session = create_proxy_session()

    try:
        # Step 0: Register OIDC client (no proxy needed - this is our client)
        print(f"\nCreating: {full_name} <{email_addr}>")
        print(f"Password: {password}")
        print(f"Proxy session: {PROXY_SESSION_ID}")

        print("[0] Registering OIDC client...")
        oidc_url = f'https://oidc.{REGION}.amazonaws.com/client/register'
        oidc_resp = requests.post(oidc_url, json={
            "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
            "clientType": "public",
            "scopes": ["codewhisperer:completions", "codewhisperer:analysis",
                       "codewhisperer:conversations", "codewhisperer:transformations",
                       "codewhisperer:taskassist"],
            "grantTypes": ["authorization_code", "refresh_token"],
            "redirectUris": [f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"],
            "issuerUrl": "https://view.awsapps.com/start"
        }, timeout=30)

        client_id = oidc_resp.json()['clientId']
        print(f"    Client ID: {client_id[:16]}...")

        # Step 1: Follow redirect chain
        print("\n[1] Following redirect chain...")
        authorize_url = (
            f'https://oidc.{REGION}.amazonaws.com/authorize'
            f'?response_type=code'
            f'&client_id={client_id}'
            f'&redirect_uri=http%3A%2F%2Flocalhost%3A{CALLBACK_PORT}%2Ftoken'
            f'&scope=codewhisperer%3Acompletions+codewhisperer%3Aanalysis'
        )

        resp = session.get(authorize_url, timeout=30, allow_redirects=True)
        current_url = resp.url
        print(f"    Final URL: {current_url[:120]}...")

        workflow_state_handle = None
        orchestrator_id = None

        if 'awsapps.com' in current_url:
            # Get orchestrator_id from URL
            match = re.search(r'orchestrator_id=([^&]+)', current_url)
            if match:
                orchestrator_id = match.group(1)
                print(f"    orchestrator_id: {orchestrator_id[:40]}...")

            # Navigate to portal.sso
            portal_url = f'https://portal.sso.{REGION}.amazonaws.com/login?directory_id=view&orchestrator_id={orchestrator_id}'
            resp2 = session.get(portal_url, timeout=30, allow_redirects=True)
            current_url = resp2.url
            print(f"    Portal URL: {current_url[:120]}...")

            # Extract WSH from HTML
            for pattern in [
                r'"workflowStateHandle"\s*:\s*"([0-9a-f-]{36})"',
                r'workflowStateHandle["\']?\s*[:=]\s*["\']?([0-9a-f-]{36})',
                r'workflowStateHandle=([0-9a-f-]{36})',
            ]:
                m = re.search(pattern, resp2.text)
                if m:
                    workflow_state_handle = m.group(1)
                    print(f"    Got WSH: {workflow_state_handle[:8]}...")
                    break

        if not workflow_state_handle:
            raise Exception(f"No WSH found. URL: {current_url[:100]}")

        # Step 2: Submit email
        print(f"\n[2] Email submit...")
        fp = make_fingerprint()

        email_payload = {
            "stepId": "get-identity-user",
            "workflowStateHandle": workflow_state_handle,
            "actionId": "SUBMIT",
            "inputs": [
                {"input_type": "UserRequestInput", "username": email_addr},
                {"input_type": "FingerPrintRequestInput", "fingerPrint": fp}
            ],
            "visitorId": str(uuid.uuid4()),
            "requestId": str(uuid.uuid4())
        }

        email_resp = session.post(
            f'https://{REGION}.signin.aws/platform/d-9067642ac7/api/execute',
            json=email_payload, timeout=60
        )
        print(f"    Email: HTTP {email_resp.status_code}")
        if email_resp.status_code == 200:
            data = email_resp.json()
            if 'workflowStateHandle' in data:
                workflow_state_handle = data['workflowStateHandle']
                print(f"    New WSH: {workflow_state_handle[:8]}...")

        time.sleep(random.uniform(1, 2))

        # Step 3: Signup
        print("[3] Signup...")
        signup_payload = {
            "stepId": "get-identity-user",
            "workflowStateHandle": workflow_state_handle,
            "actionId": "SIGNUP",
            "inputs": [
                {"input_type": "UserRequestInput", "username": email_addr},
                {"input_type": "FingerPrintRequestInput", "fingerPrint": fp}
            ],
            "visitorId": str(uuid.uuid4()),
            "requestId": str(uuid.uuid4())
        }

        signup_resp = session.post(
            f'https://{REGION}.signin.aws/platform/d-9067642ac7/api/execute',
            json=signup_payload, timeout=60
        )
        print(f"    Signup: HTTP {signup_resp.status_code}")
        signup_wsh = None
        if signup_resp.status_code == 200:
            data = signup_resp.json()
            if 'workflowStateHandle' in data:
                signup_wsh = data['workflowStateHandle']
                print(f"    Signup WSH: {signup_wsh[:8]}...")

        if not signup_wsh:
            raise Exception("Signup failed - no WSH")

        # Step 4: Use browser to load profile.aws.amazon.com SPA
        print("\n[4] Loading profile.aws.amazon.com SPA in browser...")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--proxy-server=socks5://res-us-sid-' + PROXY_SESSION_ID + ':' + PROXYRISE_API_KEY + '@gw.proxyrise.com:443',
                ]
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )
            page = context.new_page()

            # Navigate to profile.aws.amazon.com with signup WSH
            profile_url = f'https://profile.aws.amazon.com/?workflowID={signup_wsh}'
            print(f"    Navigating to: {profile_url[:80]}...")

            try:
                page.goto(profile_url, wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                print(f"    Nav timeout (expected): {type(e).__name__}")

            # Wait for SPA to render
            print("    Waiting for SPA...")
            for i in range(30):
                time.sleep(2)
                body_text = page.evaluate('document.body.innerText')
                html_len = len(page.content())
                if body_text and len(body_text) > 50:
                    print(f"    SPA loaded! Body: {body_text[:100]}")
                    break
                print(f"    [{i*2}s] body_len={len(body_text)}, html={html_len}")

            # Check current URL for workflowID
            current_profile_url = page.url
            print(f"    Current URL: {current_profile_url[:120]}...")

            # Extract workflowID from URL
            workflow_id = None
            if 'workflowID=' in current_profile_url:
                match = re.search(r'workflowID=([0-9a-f-]{36})', current_profile_url)
                if match:
                    workflow_id = match.group(1)
                    print(f"    workflowID from URL: {workflow_id}")

            if not workflow_id:
                # The SPA might have generated a new workflowID
                # Try to get it from the page state
                workflow_id = page.evaluate('''() => {
                    // Try to get workflowID from localStorage or URL
                    const url = window.location.href;
                    const match = url.match(/workflowID=([0-9a-f-]{36})/);
                    if (match) return match[1];
                    return null;
                }''')
                if workflow_id:
                    print(f"    workflowID from JS: {workflow_id}")

            if not workflow_id:
                # Use the signup WSH as fallback
                workflow_id = signup_wsh
                print(f"    Using signup WSH as workflowID: {workflow_id[:8]}...")

            # Wait longer for the SPA to make its API calls
            print("    Waiting for SPA API calls...")
            time.sleep(10)

            # Try to get the workflowState from the page
            # The SPA stores it in its internal state
            # We'll make the API calls from within the browser context
            print("    Making API calls from browser context...")

            # get-config
            config_result = page.evaluate('''async () => {
                try {
                    const resp = await fetch('/api/get-config', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({})
                    });
                    return {status: resp.status, body: await resp.text()};
                } catch(e) { return {error: e.message}; }
            }''')
            print(f"    get-config: {json.dumps(config_result)[:200]}")

            time.sleep(1)

            # get-app-context
            ctx_result = page.evaluate(f'''async () => {{
                try {{
                    const resp = await fetch('/api/get-app-context', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{"workflowID": "{workflow_id}"}})
                    }});
                    return {{status: resp.status, body: await resp.text()}};
                }} catch(e) {{ return {{error: e.message}}; }}
            }}''')
            print(f"    get-app-context: {json.dumps(ctx_result)[:200]}")

            time.sleep(1)

            # start
            start_result = page.evaluate(f'''async () => {{
                try {{
                    const resp = await fetch('/api/start', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            "workflowID": "{workflow_id}",
                            "browserData": {{
                                "attributes": {{
                                    "fingerprint": "ECdITeCs:" + btoa(String.fromCharCode(...new Uint8Array(4000).map(() => Math.floor(Math.random()*256)))),
                                    "eventTimestamp": new Date().toISOString(),
                                    "timeSpentOnPage": "5000",
                                    "eventType": "PageLoad",
                                    "ubid": "118-" + Math.floor(Math.random()*900000+100000) + "-" + Math.floor(Math.random()*9000000+1000000)
                                }},
                                "cookies": {{}}
                            }}
                        }})
                    }});
                    return {{status: resp.status, body: await resp.text()}};
                }} catch(e) {{ return {{error: e.message}}; }}
            }}''')
            print(f"    start: {json.dumps(start_result)[:300]}")

            # Extract workflowState from start response
            workflow_state = None
            if start_result.get('status') == 200:
                try:
                    start_data = json.loads(start_result['body'])
                    workflow_state = start_data.get('workflowState') or start_data.get('state')
                    print(f"    workflowState: {workflow_state[:20] if workflow_state else 'None'}...")
                except:
                    pass

            if workflow_state:
                # Fill name in the form
                print("\n[5] Filling name form...")
                page.wait_for_timeout(2000)

                # Look for name input
                name_input = page.locator('input[type="text"], input[name*="name"], input[placeholder*="name"], input[aria-label*="name"]').first
                if name_input.is_visible():
                    # Human-like typing
                    for char in full_name:
                        name_input.type(char, delay=random.uniform(50, 150))
                        if random.random() < 0.1:
                            page.wait_for_timeout(random.randint(100, 500))
                    print(f"    Name filled: {full_name}")
                    page.wait_for_timeout(random.uniform(500, 1500))

                    # Click Continue button
                    continue_btn = page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("continue")').first
                    if continue_btn.is_visible():
                        continue_btn.click()
                        print("    Continue clicked")
                    else:
                        # Try pressing Enter
                        name_input.press('Enter')
                        print("    Enter pressed")
                else:
                    print("    Name input not found")

                # Wait for OTP page
                print("    Waiting for OTP page...")
                page.wait_for_timeout(5000)
                body = page.evaluate('document.body.innerText')
                print(f"    Body: {body[:200]}")

                # Get OTP from Gmail
                print("\n[6] Getting OTP...")
                otp = get_otp_from_gmail(email_addr, timeout=60)
                if not otp:
                    print("    Waiting 30s more...")
                    time.sleep(30)
                    otp = get_otp_from_gmail(email_addr, timeout=60)

                if otp:
                    print(f"    OTP: {otp}")
                    # Fill OTP
                    otp_input = page.locator('input[type="text"], input[name*="otp"], input[placeholder*="code"], input[aria-label*="code"]').first
                    if otp_input.is_visible():
                        otp_input.type(otp, delay=random.uniform(100, 200))
                        page.wait_for_timeout(random.uniform(500, 1000))
                        # Submit
                        submit_btn = page.locator('button[type="submit"], button:has-text("Verify"), button:has-text("verify")').first
                        if submit_btn.is_visible():
                            submit_btn.click()
                        else:
                            otp_input.press('Enter')
                        print("    OTP submitted")
                else:
                    print("    No OTP found!")

                # Wait for password page
                print("    Waiting for password page...")
                page.wait_for_timeout(5000)
                body = page.evaluate('document.body.innerText')
                print(f"    Body: {body[:200]}")

                # Fill password
                pw_input = page.locator('input[type="password"]').first
                if pw_input.is_visible():
                    for char in password:
                        pw_input.type(char, delay=random.uniform(50, 150))
                    print("    Password filled")
                    page.wait_for_timeout(random.uniform(500, 1000))

                    submit_btn = page.locator('button[type="submit"], button:has-text("Create"), button:has-text("create")').first
                    if submit_btn.is_visible():
                        submit_btn.click()
                    else:
                        pw_input.press('Enter')
                    print("    Password submitted")

                # Wait for token
                print("    Waiting for token...")
                for i in range(20):
                    page.wait_for_timeout(3000)
                    if 'refresh_token' in token_store:
                        print(f"    TOKEN CAPTURED!")
                        result['refresh_token'] = token_store['refresh_token']
                        result['status'] = 'SUCCESS'
                        break
                    current_body = page.evaluate('document.body.innerText')
                    if 'error' in current_body.lower() or 'ERR' in current_body:
                        print(f"    Error detected: {current_body[:200]}")
                        break
                    print(f"    [{i*3}s] waiting... body: {current_body[:50]}")

            browser.close()

        if 'refresh_token' not in result:
            result['status'] = 'PARTIAL'
            result['error'] = 'No token captured'

    except Exception as e:
        result['status'] = 'FAILED'
        result['error'] = str(e)
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()

    return result


if __name__ == '__main__':
    print("=" * 70)
    print("Hybrid Kiro Account Creator")
    print("API for sign-in + Browser for profile SPA")
    print("=" * 70)

    # Start token callback server
    token_server = HTTPServer(('127.0.0.1', CALLBACK_PORT), TokenCallbackHandler)
    token_thread = threading.Thread(target=token_server.serve_forever, daemon=True)
    token_thread.start()
    print(f"Token callback server on port {CALLBACK_PORT}")

    result = create_account()

    print(f"\n{'='*70}")
    print(f"Status: {result['status']}")
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

    print(f"\nTotal: {len(existing)}, Success: {sum(1 for r in existing if r.get('status')=='SUCCESS')}")
