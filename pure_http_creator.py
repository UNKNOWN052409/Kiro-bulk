"""
Kiro Account Creator - Pure HTTP/requests based (NO BROWSER for API calls)
All API requests go through ProxyRise SOCKS5 residential proxy.
Browser is only used ONCE to generate the fingerprint.

CORRECTED FLOW (based on browser captures):
1. "" + FP → stepId=""
2. "start" + FP → stepId="start"
3. "get-identity-user" SUBMIT + email → stepId="get-identity-user"
4. "get-identity-user" SIGNUP + email → 400 ENTITY_DOES_NOT_EXIST
5. "" + User + FP → stepId="user-signup" + redirect to /signup
6. "start" + User + FP (signup) → stepId="start"
7. "user-signup" SUBMIT + name → stepId=get-otp (or similar)
8. OTP step SUBMIT + otp → stepId=password-creation
9. Password SUBMIT + password → redirect with auth code
10. Exchange code for tokens
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
import imaplib
from urllib.parse import quote, urlparse

# ==================== CONFIG ====================
REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]
CALLBACK_PORT = 9997
DIRECTORY_ID = 'd-9067642ac7'
EXECUTE_URL = f'https://us-east-1.signin.aws/platform/{DIRECTORY_ID}/api/execute'

# ProxyRise SOCKS5
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
SOCKS5_HOST = 'gw.proxyrise.com'
SOCKS5_PORT = 443

# Gmail
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

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
FINGERPRINT_FILE = '/home/ubuntu/kiro-gen/fingerprint.txt'


def load_or_generate_fingerprint():
    """Load fingerprint from file or generate using browser."""
    try:
        with open(FINGERPRINT_FILE, 'r') as f:
            fp = f.read().strip()
            if fp and fp.startswith('ECdITeCs:'):
                print("  Loaded fingerprint from file")
                return fp
    except:
        pass
    
    # Generate using browser
    from playwright.sync_api import sync_playwright
    
    print("  Generating fingerprint via browser...")
    
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
    
    session = requests.Session()
    session.headers.update({'User-Agent': UA})
    resp = session.get(auth_url, allow_redirects=True, timeout=30)
    start_url = resp.url
    resp2 = session.get('https://portal.sso.us-east-1.amazonaws.com/login',
                        params={'directory_id': 'view', 'redirect_url': start_url}, timeout=30)
    login_data = resp2.json()
    signin_url = login_data['redirectUrl']
    csrf_token = login_data['csrfToken']
    
    captured_fp = None
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=UA, locale='en-US', ignore_https_errors=True)
        context.add_cookies([{'name': 'loginCsrfToken', 'value': csrf_token, 'domain': '.signin.aws', 'path': '/', 'secure': True, 'sameSite': 'Lax'}])
        page = context.new_page()
        
        def handle_request(route, request):
            nonlocal captured_fp
            if '/api/execute' in request.url and request.post_data:
                try:
                    body = json.loads(request.post_data)
                    for inp in body.get('inputs', []):
                        if inp.get('input_type') == 'FingerPrintRequestInput':
                            captured_fp = inp['fingerPrint']
                            break
                except:
                    pass
            route.continue_()
        
        page.route('**/*', handle_request)
        page.goto(signin_url, wait_until='domcontentloaded', timeout=60000)
        
        for i in range(30):
            time.sleep(0.5)
            if captured_fp:
                break
        
        browser.close()
    
    if captured_fp:
        with open(FINGERPRINT_FILE, 'w') as f:
            f.write(captured_fp)
        print("  Fingerprint saved to file")
    
    return captured_fp


def get_otp_from_gmail(email_addr, timeout=120):
    """Get OTP from Gmail inbox."""
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
        except Exception as e:
            print(f"    Gmail error: {e}")
            time.sleep(3)
    return None


def make_proxy_session():
    """Create a requests session through ProxyRise SOCKS5 residential proxy."""
    s = requests.Session()
    session_id = f'res-us-sid-{random.randint(10000000, 999999999)}'
    proxy_url = f'socks5://{session_id}:{PROXYRISE_API_KEY}@{SOCKS5_HOST}:{SOCKS5_PORT}'
    s.proxies = {'http': proxy_url, 'https': proxy_url}
    s.headers.update({
        'User-Agent': UA,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Content-Type': 'application/json',
        'Origin': 'https://us-east-1.signin.aws',
    })
    return s


def execute_step(session, workflow_state_handle, step_id, inputs, action_id=None, visitor_id=None):
    """Make a POST request to the execute API through the proxy."""
    body = {
        "stepId": step_id,
        "workflowStateHandle": workflow_state_handle,
        "inputs": inputs,
        "requestId": str(uuid.uuid4())
    }
    if action_id:
        body["actionId"] = action_id
    if visitor_id:
        body["visitorId"] = visitor_id
    
    try:
        resp = session.post(EXECUTE_URL, json=body, timeout=30)
        try:
            return resp.json()
        except:
            return {'_raw': resp.text[:500], '_status': resp.status_code}
    except Exception as e:
        return {'_error': str(e)}


def get_error_code(result):
    """Extract error code from response."""
    if isinstance(result.get('message'), dict):
        return result['message'].get('errorCode', '')
    return ''


def create_account(email=None):
    """Create a Kiro AI account using pure HTTP requests through residential proxy."""
    
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = email or f'{prefix}@havenhaus.in'
    chars = string.ascii_letters + string.digits + '!@#$%'
    password = ''.join(random.choices(chars, k=random.randint(14, 18)))
    if not any(c.isupper() for c in password):
        password = password[:-1] + random.choice(string.ascii_uppercase)
    if not any(c.isdigit() for c in password):
        password = password[:-2] + random.choice(string.digits) + password[-1]
    if not any(not c.isalnum() for c in password):
        password = password[:-1] + random.choice('!@#$%')
    
    visitor_id = str(uuid.uuid4())
    
    print(f"\n{'='*70}")
    print(f"Creating: {full_name} <{email}>")
    print(f"Password: {password}")
    print(f"{'='*70}")
    
    # ==================== STEP 0: Register OIDC client ====================
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
    print(f"    Client ID: {client_id}")
    
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
    
    # ==================== STEP 1: Get signin URL ====================
    print("\n[1] Getting signin URL...")
    no_proxy = requests.Session()
    no_proxy.headers.update({'User-Agent': UA})
    resp = no_proxy.get(auth_url, allow_redirects=True, timeout=30)
    start_url = resp.url
    resp2 = no_proxy.get('https://portal.sso.us-east-1.amazonaws.com/login',
                         params={'directory_id': 'view', 'redirect_url': start_url}, timeout=30)
    login_data = resp2.json()
    signin_url = login_data['redirectUrl']
    
    wsh_match = re.search(r'workflowStateHandle=([a-f0-9-]+)', signin_url)
    initial_wsh = wsh_match.group(1) if wsh_match else ''
    print(f"    Initial WSH: {initial_wsh}")
    
    # ==================== STEP 2: Get fingerprint ====================
    print("\n[2] Getting fingerprint...")
    fingerprint = load_or_generate_fingerprint()
    if not fingerprint:
        print("    ERROR: Could not get fingerprint")
        return None
    fp_inputs = [{"input_type": "FingerPrintRequestInput", "fingerPrint": fingerprint}]
    print(f"    FP: {fingerprint[:40]}...")
    
    # ==================== STEP 3: Switch to residential proxy ====================
    print("\n[3] Switching to residential proxy...")
    proxy_session = make_proxy_session()
    
    # Verify proxy
    try:
        test_resp = proxy_session.get('https://api.ipquery.io/?format=json', timeout=30)
        ip_data = test_resp.json()
        print(f"    Proxy IP: {ip_data.get('ip', 'unknown')}")
    except Exception as e:
        print(f"    Proxy test error: {e}")
    
    # ==================== STEP 4: "" (empty stepId) + FP ====================
    print("\n[4] Step '': initial call...")
    result = execute_step(proxy_session, initial_wsh, "", fp_inputs)
    if '_error' in result:
        print(f"    ERROR: {result['_error']}")
        return None
    new_wsh = result.get('workflowStateHandle', '')
    print(f"    stepId={result.get('stepId', 'N/A')}, WSH: {new_wsh[:20]}...")
    if not new_wsh:
        print(f"    ERROR: No WSH. Response: {json.dumps(result)[:200]}")
        return None
    
    # ==================== STEP 5: "start" + FP ====================
    print("\n[5] Step 'start'...")
    result = execute_step(proxy_session, new_wsh, "start", fp_inputs, visitor_id=visitor_id)
    if '_error' in result:
        print(f"    ERROR: {result['_error']}")
        return None
    new_wsh = result.get('workflowStateHandle', new_wsh)
    print(f"    stepId={result.get('stepId', 'N/A')}, WSH: {new_wsh[:20]}...")
    if not new_wsh:
        print(f"    ERROR: No WSH. Response: {json.dumps(result)[:200]}")
        return None
    
    # ==================== STEP 6: Email SUBMIT ====================
    print("\n[6] Email SUBMIT (get-identity-user)...")
    email_inputs = [
        {"input_type": "UserRequestInput", "username": email},
        {"input_type": "ApplicationTypeRequestInput", "applicationType": "SSO_INDIVIDUAL_ID"},
        {"input_type": "UserEventRequestInput", "directoryId": DIRECTORY_ID, "userName": email,
         "userEvents": [{"input_type": "UserEvent", "eventType": "PAGE_SUBMIT", "pageName": "IDENTIFICATION",
                         "timeSpentOnPage": random.randint(1000, 5000)}]},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": fingerprint}
    ]
    result = execute_step(proxy_session, new_wsh, "get-identity-user", email_inputs, action_id="SUBMIT", visitor_id=visitor_id)
    err = get_error_code(result)
    new_wsh = result.get('workflowStateHandle', new_wsh)
    resp_step = result.get('stepId', '')
    print(f"    stepId={resp_step}, error={err}, WSH: {new_wsh[:20]}...")
    print(f"    Full response: {json.dumps(result)[:500]}")
    
    # ==================== SIGNUP action (needed for new users) ====================
    # The browser sends SIGNUP after email SUBMIT to trigger the signup flow
    print("\n[7] SIGNUP action...")
    signup_inputs = [
        {"input_type": "UserRequestInput", "username": email},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": fingerprint}
    ]
    result = execute_step(proxy_session, new_wsh, "get-identity-user", signup_inputs, action_id="SIGNUP", visitor_id=visitor_id)
    err = get_error_code(result)
    # Expected: 400 ENTITY_DOES_NOT_EXIST (or the response might be different)
    print(f"    SIGNUP error={err} (expected ENTITY_DOES_NOT_EXIST)")
    
    # ==================== Get user-signup step ====================
    # After SIGNUP, send "" + User + FP to get the user-signup step
    print("\n[8] Step '' + User → user-signup...")
    user_inputs = [
        {"input_type": "UserRequestInput", "username": email},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": fingerprint}
    ]
    result = execute_step(proxy_session, new_wsh, "", user_inputs, visitor_id=visitor_id)
    if '_error' in result:
        print(f"    ERROR: {result['_error']}")
        return None
    
    step_id = result.get('stepId', '')
    new_wsh = result.get('workflowStateHandle', new_wsh)
    print(f"    stepId={step_id}, WSH: {new_wsh[:20]}...")
    
    # Get redirect URL for signup
    redirect_url = result.get('redirect', {}).get('url', '')
    if redirect_url:
        signup_wsh_match = re.search(r'workflowStateHandle=([a-f0-9-]+)', redirect_url)
        if signup_wsh_match:
            new_wsh = signup_wsh_match.group(1)
            print(f"    Signup WSH from redirect: {new_wsh[:20]}...")
    
    # ==================== STEP 8: "start" on signup flow ====================
    print("\n[8] Step 'start' (signup)...")
    result = execute_step(proxy_session, new_wsh, "start", user_inputs, visitor_id=visitor_id)
    if '_error' in result:
        print(f"    ERROR: {result['_error']}")
        return None
    new_wsh = result.get('workflowStateHandle', new_wsh)
    print(f"    stepId={result.get('stepId', 'N/A')}, WSH: {new_wsh[:20]}...")
        
    # ==================== STEP 9: Name SUBMIT (user-signup) ====================
    print("\n[9] Name SUBMIT (user-signup)...")
    name_inputs = [
        {"input_type": "UserRequestInput", "username": email},
        {"input_type": "NameRequestInput", "name": full_name},
        {"input_type": "ApplicationTypeRequestInput", "applicationType": "SSO_INDIVIDUAL_ID"},
        {"input_type": "UserEventRequestInput", "directoryId": DIRECTORY_ID, "userName": email,
         "userEvents": [{"input_type": "UserEvent", "eventType": "PAGE_SUBMIT", "pageName": "NAME",
                         "timeSpentOnPage": random.randint(1000, 5000)}]},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": fingerprint}
    ]
    result = execute_step(proxy_session, new_wsh, "user-signup", name_inputs, action_id="SUBMIT", visitor_id=visitor_id)
    if '_error' in result:
        print(f"    ERROR: {result['_error']}")
        print(f"    Raw: {result.get('_raw', '')[:300]}")
        return None
    err = get_error_code(result)
    new_wsh = result.get('workflowStateHandle', new_wsh)
    resp_step = result.get('stepId', '')
    print(f"    stepId={resp_step}, error={err}, WSH: {new_wsh[:20]}...")
    
    if err:
        print(f"    ERROR response: {json.dumps(result)[:300]}")
        return None
    
    # ==================== STEP 10: OTP ====================
    print("\n[10] Getting OTP...")
    otp = get_otp_from_gmail(email)
    if not otp:
        print("    ERROR: No OTP received")
        return None
    print(f"    OTP: {otp}")
    
    # Determine OTP step - might be from previous response or guess
    otp_step = resp_step if resp_step else 'get-email-otp'
    if 'otp' not in otp_step.lower() and 'verify' not in otp_step.lower():
        otp_step = 'get-email-otp'
    
    otp_inputs = [
        {"input_type": "OtpRequestInput", "otp": otp},
        {"input_type": "UserRequestInput", "username": email},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": fingerprint}
    ]
    
    # Try the determined step first, then fallback
    result = execute_step(proxy_session, new_wsh, otp_step, otp_inputs, action_id="SUBMIT", visitor_id=visitor_id)
    if '_error' in result:
        # Try alternate step names
        for alt_step in ['verify-otp', 'get-otp', 'otp-verification']:
            result = execute_step(proxy_session, new_wsh, alt_step, otp_inputs, action_id="SUBMIT", visitor_id=visitor_id)
            if '_error' not in result:
                otp_step = alt_step
                break
        else:
            print(f"    ERROR: {result['_error']}")
            return None
    
    err = get_error_code(result)
    new_wsh = result.get('workflowStateHandle', new_wsh)
    print(f"    OTP stepId={result.get('stepId', 'N/A')}, error={err}")
    
    if err:
        print(f"    ERROR response: {json.dumps(result)[:300]}")
        return None
    
    # ==================== STEP 11: Password ====================
    print("\n[11] Setting password...")
    pw_step = result.get('stepId', '')
    if 'password' not in pw_step.lower() and 'pw' not in pw_step.lower():
        pw_step = 'password-creation'
    
    pw_inputs = [
        {"input_type": "PasswordRequestInput", "password": password},
        {"input_type": "UserRequestInput", "username": email},
        {"input_type": "FingerPrintRequestInput", "fingerPrint": fingerprint}
    ]
    
    result = execute_step(proxy_session, new_wsh, pw_step, pw_inputs, action_id="SUBMIT", visitor_id=visitor_id)
    if '_error' in result:
        # Try alternate
        result = execute_step(proxy_session, new_wsh, 'create-password', pw_inputs, action_id="SUBMIT", visitor_id=visitor_id)
        if '_error' in result:
            print(f"    ERROR: {result['_error']}")
            return None
    
    err = get_error_code(result)
    print(f"    PW stepId={result.get('stepId', 'N/A')}, error={err}")
    
    # Check for redirect with auth code
    redirect = result.get('redirect', {})
    redirect_url = redirect.get('url', '')
    print(f"    Redirect: {redirect_url[:100]}")
    
    if redirect_url:
        code_match = re.search(r'code=([^&]+)', redirect_url)
        if code_match:
            auth_code = code_match.group(1)
            print(f"    Auth code: {auth_code[:20]}...")
            
            # Exchange for tokens
            print("\n[12] Exchanging code for tokens...")
            token_resp = requests.post(f'{OIDC_BASE}/token', data={
                'grant_type': 'authorization_code',
                'client_id': client_id,
                'code': auth_code,
                'code_verifier': code_verifier,
                'redirect_uri': redirect_uri
            }, timeout=10)
            
            if token_resp.status_code == 200:
                token_data = token_resp.json()
                print(f"    SUCCESS! Tokens obtained")
                return {
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
            else:
                print(f"    Token exchange failed: {token_resp.text[:200]}")
                print(f"    Full redirect: {redirect_url}")
    
    return {'email': email, 'name': full_name, 'password': password, 'error': 'flow_incomplete', 'last_response': result}


def main():
    print("=" * 70)
    print("Kiro AI Account Creator - Pure HTTP via Residential Proxy")
    print("=" * 70)
    
    # Pre-generate fingerprint
    print("\nPre-generating fingerprint...")
    fp = load_or_generate_fingerprint()
    if not fp:
        print("ERROR: Could not generate fingerprint")
        return
    
    print(f"\nFingerprint ready: {fp[:40]}...")
    
    # Create account
    result = create_account()
    
    if result and result.get('access_token'):
        print(f"\n{'='*70}")
        print(f"SUCCESS!")
        print(f"  Email: {result['email']}")
        print(f"  Name: {result['name']}")
        print(f"  Password: {result['password']}")
        print(f"  Access Token: {result['access_token'][:40]}...")
        print(f"  Refresh Token: {result['refresh_token'][:40]}...")
        print(f"{'='*70}")
        
        # Save to file
        accounts = []
        try:
            with open('/home/ubuntu/kiro-gen/accounts.json', 'r') as f:
                accounts = json.load(f)
        except:
            pass
        accounts.append(result)
        with open('/home/ubuntu/kiro-gen/accounts.json', 'w') as f:
            json.dump(accounts, f, indent=2)
        print(f"\nAccount saved to accounts.json ({len(accounts)} total)")
    elif result:
        print(f"\nPartial/Failed: {json.dumps(result, default=str)[:500]}")
    else:
        print("\nFAILED")


if __name__ == '__main__':
    main()
