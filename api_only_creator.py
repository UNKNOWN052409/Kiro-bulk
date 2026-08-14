"""
Kiro AI Account Creator - Pure API Approach
Makes AWS signup API calls directly through the persistent SOCKS5 session.
No browser needed for the signup flow.
Only uses browser for OIDC authorize (which is fast without proxy).
"""

import uuid, secrets, hashlib, base64, requests, json, time, socket, threading, http.server, random, re
from urllib.parse import quote, urlparse, parse_qs

# Import the persistent SOCKS5 session
from socks5_session import Socks5Session

# Config
REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"]
CALLBACK_PORT = 9997
DIRECTORY_ID = 'd-9067642ac7'
UAMOBILE = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

# ProxyRise config
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_HOST = 'gw.proxyrise.com'
PROXY_PORT = 443

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'Mia', 'James', 'Charlotte', 'Benjamin', 'Amelia', 'Lucas', 'Harper', 'Henry', 'Evelyn', 'Alexander',
               'Sebastian', 'Jack', 'Owen', 'Theodore', 'Aria', 'Scarlett', 'Victoria', 'Madison', 'Luna', 'Grace']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
              'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson',
              'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker', 'Young', 'Allen', 'King', 'Wright', 'Scott']


def extract_otp():
    import imaplib, email as email_lib
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


def make_fingerprint():
    """Generate a realistic browser fingerprint."""
    import base64
    # Simulate Chrome's fingerprint format
    fingerprint = f"ECdITeCs:{base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')[:43]}"
    return fingerprint


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
    
    # Create persistent SOCKS5 session (one connection = one IP)
    print("[0] Creating persistent SOCKS5 session...")
    session = Socks5Session(
        host=PROXY_HOST, port=PROXY_PORT,
        username='res-us', password=PROXYRISE_API_KEY
    )
    
    # Check IP
    proxy_ip = session.get_ip()
    print(f"    Proxy IP: {proxy_ip}")
    if not proxy_ip:
        print("    [!] Proxy not working!")
        return
    
    # Common headers for API calls
    api_headers = {
        'User-Agent': UAMOBILE,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'identity',
        'Content-Type': 'application/json',
        'Origin': 'https://us-east-1.signin.aws',
        'Referer': f'https://us-east-1.signin.aws/platform/{DIRECTORY_ID}/login',
    }
    
    # STATE MACHINE:
    # Step 1: Initial page load (stepId: "")
    print("[1] Step: initial load (stepId='')...")
    fingerprint = make_fingerprint()
    payload = {
        "stepId": "",
        "workflowStateHandle": str(uuid.uuid4()),
        "inputs": [{"input_type": "FingerPrintRequestInput", "fingerPrint": fingerprint}]
    }
    resp = session.request('POST', 
        f'https://us-east-1.signin.aws/platform/{DIRECTORY_ID}/api/execute',
        headers=api_headers, body=json.dumps(payload))
    
    if not resp or resp.status_code != 200:
        print(f"    [!] Failed: status={resp.status_code if resp else 'N/A'}")
        return
    
    data = resp.json()
    workflow_state = data.get('workflowStateHandle', '')
    current_step = data.get('stepId', '')
    print(f"    Response: step={current_step}, new_state={workflow_state}")
    
    # Step 2: get-identity-user (email form)
    print("[2] Step: get-identity-user...")
    payload = {
        "stepId": current_step,
        "workflowStateHandle": workflow_state,
        "inputs": [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()}]
    }
    resp = session.request('POST',
        f'https://us-east-1.signin.aws/platform/{DIRECTORY_ID}/api/execute',
        headers=api_headers, body=json.dumps(payload))
    
    if not resp or resp.status_code != 200:
        print(f"    [!] Failed: status={resp.status_code if resp else 'N/A'}")
        print(f"    Body: {resp.text[:200] if resp else 'N/A'}")
        return
    
    data = resp.json()
    workflow_state = data.get('workflowStateHandle', '')
    current_step = data.get('stepId', '')
    print(f"    Response: step={current_step}, new_state={workflow_state}")
    
    # Step 3: Submit email (get-identity-user with email input)
    print(f"[3] Step: submit email ({email})...")
    payload = {
        "stepId": current_step,
        "workflowStateHandle": workflow_state,
        "inputs": [
            {"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()},
            {"input_type": "TextInput", "key": "identity", "value": email}
        ]
    }
    resp = session.request('POST',
        f'https://us-east-1.signin.aws/platform/{DIRECTORY_ID}/api/execute',
        headers=api_headers, body=json.dumps(payload))
    
    if not resp or resp.status_code != 200:
        print(f"    [!] Failed: status={resp.status_code if resp else 'N/A'}")
        print(f"    Body: {resp.text[:200] if resp else 'N/A'}")
        return
    
    data = resp.json()
    workflow_state = data.get('workflowStateHandle', '')
    current_step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '')
    print(f"    Response: step={current_step}, new_state={workflow_state}" + (f", error={error}" if error else ""))
    
    # The response should redirect to user-signup
    # Step 4: Follow redirect to profile.aws.amazon.com (user-signup step)
    print("[4] Step: follow redirect to profile.aws.amazon.com...")
    
    # The SPA would normally redirect here. We need to make the request to the new endpoint.
    # The redirect URL is in the response data
    redirect_url = data.get('redirectUri', '')
    if not redirect_url:
        # Try to find it in the response
        for key, val in data.items():
            if isinstance(val, str) and 'profile.aws.amazon.com' in val:
                redirect_url = val
                break
    
    if redirect_url:
        print(f"    Redirect to: {redirect_url[:80]}")
    else:
        print("    No redirect URL found, trying profile.aws.amazon.com directly...")
        redirect_url = 'https://profile.aws.amazon.com/'
    
    # Update headers for profile.aws.amazon.com
    profile_headers = {
        'User-Agent': UAMOBILE,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'identity',
        'Content-Type': 'application/json',
        'Origin': 'https://profile.aws.amazon.com',
        'Referer': 'https://profile.aws.amazon.com/',
    }
    
    # Make the user-signup call on profile.aws.amazon.com
    # First, get the signup page (step: start)
    print("[5] Step: profile.aws.amazon.com signup start...")
    payload = {
        "stepId": "",
        "workflowStateHandle": str(uuid.uuid4()),
        "inputs": [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()}]
    }
    resp = session.request('POST',
        'https://profile.aws.amazon.com/api/execute',
        headers=profile_headers, body=json.dumps(payload))
    
    if not resp or resp.status_code != 200:
        print(f"    [!] Failed: status={resp.status_code if resp else 'N/A'}")
        print(f"    Body: {resp.text[:200] if resp else 'N/A'}")
        return
    
    data = resp.json()
    workflow_state = data.get('workflowStateHandle', '')
    current_step = data.get('stepId', '')
    print(f"    Response: step={current_step}, new_state={workflow_state}")
    
    # Step 6: get-verified-username (name form)
    print("[6] Step: get-verified-username (name form)...")
    payload = {
        "stepId": current_step,
        "workflowStateHandle": workflow_state,
        "inputs": [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()}]
    }
    resp = session.request('POST',
        'https://profile.aws.amazon.com/api/execute',
        headers=profile_headers, body=json.dumps(payload))
    
    if not resp or resp.status_code != 200:
        print(f"    [!] Failed: status={resp.status_code if resp else 'N/A'}")
        print(f"    Body: {resp.text[:200] if resp else 'N/A'}")
        return
    
    data = resp.json()
    workflow_state = data.get('workflowStateHandle', '')
    current_step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '')
    print(f"    Response: step={current_step}, new_state={workflow_state}" + (f", error={error}" if error else ""))
    
    # Step 7: Submit name
    print(f"[7] Step: submit name ({full_name})...")
    payload = {
        "stepId": current_step,
        "workflowStateHandle": workflow_state,
        "inputs": [
            {"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()},
            {"input_type": "TextInput", "key": "verifiedUserName", "value": full_name}
        ]
    }
    resp = session.request('POST',
        'https://profile.aws.amazon.com/api/execute',
        headers=profile_headers, body=json.dumps(payload))
    
    if not resp or resp.status_code != 200:
        print(f"    [!] Failed: status={resp.status_code if resp else 'N/A'}")
        print(f"    Body: {resp.text[:200] if resp else 'N/A'}")
        return
    
    data = resp.json()
    workflow_state = data.get('workflowStateHandle', '')
    current_step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '')
    print(f"    Response: step={current_step}, new_state={workflow_state}" + (f", error={error}" if error else ""))
    
    # Step 8: send-otp (trigger OTP email)
    print("[8] Step: send-otp...")
    payload = {
        "stepId": current_step,
        "workflowStateHandle": workflow_state,
        "inputs": [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()}]
    }
    resp = session.request('POST',
        'https://profile.aws.amazon.com/api/execute',
        headers=profile_headers, body=json.dumps(payload))
    
    if not resp or resp.status_code != 200:
        print(f"    [!] Failed: status={resp.status_code if resp else 'N/A'}")
        print(f"    Body: {resp.text[:200] if resp else 'N/A'}")
        return
    
    data = resp.json()
    workflow_state = data.get('workflowStateHandle', '')
    current_step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '')
    print(f"    Response: step={current_step}, new_state={workflow_state}" + (f", error={error}" if error else ""))
    
    # Step 9: Submit OTP
    print("[9] Step: fetch OTP from Gmail...")
    otp = None
    for attempt in range(20):
        otp = extract_otp()
        if otp:
            break
        time.sleep(5)
    
    if not otp:
        print("    [!] No OTP received!")
        return
    
    print(f"    OTP: {otp}")
    print("[10] Step: submit OTP...")
    payload = {
        "stepId": current_step,
        "workflowStateHandle": workflow_state,
        "inputs": [
            {"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()},
            {"input_type": "TextInput", "key": "otp", "value": otp}
        ]
    }
    resp = session.request('POST',
        'https://profile.aws.amazon.com/api/execute',
        headers=profile_headers, body=json.dumps(payload))
    
    if not resp or resp.status_code != 200:
        print(f"    [!] Failed: status={resp.status_code if resp else 'N/A'}")
        print(f"    Body: {resp.text[:200] if resp else 'N/A'}")
        return
    
    data = resp.json()
    workflow_state = data.get('workflowStateHandle', '')
    current_step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '')
    print(f"    Response: step={current_step}, new_state={workflow_state}" + (f", error={error}" if error else ""))
    
    # Step 11: Set password
    print("[11] Step: set password...")
    payload = {
        "stepId": current_step,
        "workflowStateHandle": workflow_state,
        "inputs": [
            {"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()},
            {"input_type": "PasswordInput", "key": "password", "value": password},
            {"input_type": "PasswordInput", "key": "confirmPassword", "value": password}
        ]
    }
    resp = session.request('POST',
        'https://profile.aws.amazon.com/api/execute',
        headers=profile_headers, body=json.dumps(payload))
    
    if not resp or resp.status_code != 200:
        print(f"    [!] Failed: status={resp.status_code if resp else 'N/A'}")
        print(f"    Body: {resp.text[:200] if resp else 'N/A'}")
        return
    
    data = resp.json()
    workflow_state = data.get('workflowStateHandle', '')
    current_step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '')
    print(f"    Response: step={current_step}, new_state={workflow_state}" + (f", error={error}" if error else ""))
    
    print("\n[FINAL] Account creation API flow complete!")
    print(f"    Email: {email}")
    print(f"    Password: {password}")
    print(f"    Name: {full_name}")
    print(f"    Final step: {current_step}")
    
    # Now we need to complete the OIDC flow to get the token
    # The account is created but we need to login through OIDC to get the auth code
    print("\n[12] Completing OIDC flow to get token...")
    
    # Register OIDC client
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
    oidc_state = secrets.token_urlsafe(16)
    redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={quote(redirect_uri)}&scopes={quote(" ".join(GRANT_SCOPES))}'
                f'&state={oidc_state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    # Start callback server
    CallbackHandler.captured_code = None
    callback_server = http.server.HTTPServer(('127.0.0.1', CALLBACK_PORT), CallbackHandler)
    callback_server.daemon_threads = True
    threading.Thread(target=callback_server.serve_forever, daemon=True).start()
    
    # Use browser for OIDC flow (no proxy needed - it's fast)
    print("[13] Launching browser for OIDC login...")
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=UAMOBILE,
            locale='en-US',
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        
        page.goto(auth_url, wait_until='commit', timeout=30000)
        print("    OIDC page loaded!")
        
        # Wait for email form
        print("[14] Waiting for email form...")
        for i in range(30):
            time.sleep(1)
            try:
                email_input = page.locator('input[type="email"]').first
                if email_input.is_visible(timeout=2000):
                    print(f"    Email form ready at {i}s!")
                    email_input.fill(email)
                    time.sleep(0.5)
                    page.locator('button:has-text("Continue")').first.click()
                    print("    Email submitted!")
                    break
            except:
                pass
        
        # Wait for password form
        print("[15] Waiting for password form...")
        time.sleep(5)
        try:
            pw_input = page.locator('input[type="password"]').first
            if pw_input.is_visible(timeout=5000):
                pw_input.fill(password)
                time.sleep(0.5)
                page.locator('button:has-text("Sign in")').first.click()
                print("    Password submitted!")
        except Exception as e:
            print(f"    Password error: {e}")
        
        # Wait for token redirect
        print("[16] Waiting for token redirect...")
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
        
        browser.close()
    
    callback_server.shutdown()
    
    # Exchange code for token
    if CallbackHandler.captured_code:
        print("[17] Exchanging auth code for token...")
        token_resp = requests.post(f'{OIDC_BASE}/token', json={
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'code': CallbackHandler.captured_code,
            'code_verifier': code_verifier,
            'redirect_uri': redirect_uri
        }, timeout=10)
        
        if token_resp.status_code == 200:
            token_data = token_resp.json()
            access_token = token_data.get('access_token', '')
            print(f"    Access token: {access_token[:50]}...")
            
            # Save result
            result = {
                'email': email,
                'password': password,
                'name': full_name,
                'auth_code': CallbackHandler.captured_code,
                'access_token': access_token,
                'proxy_ip': proxy_ip,
            }
            with open('/home/ubuntu/kiro-gen/last_result.json', 'w') as f:
                json.dump(result, f, indent=2)
            print("\n    SUCCESS! Account created and token captured.")
        else:
            print(f"    Token exchange failed: {token_resp.status_code}")
            print(f"    Body: {token_resp.text[:200]}")
    else:
        print("    No auth code captured!")
    
    session.close()


if __name__ == '__main__':
    main()
