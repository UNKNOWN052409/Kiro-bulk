"""
Test the full Kiro AI account creation flow WITHOUT proxy.
This confirms the API state machine works. Then we can add proxy later.
"""

import uuid, secrets, hashlib, base64, requests, json, time, threading, http.server, random, re
from urllib.parse import quote, urlparse, parse_qs
from playwright.sync_api import sync_playwright

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"]
CALLBACK_PORT = 9997
DIRECTORY_ID = 'd-9067642ac7'
UAMOBILE = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'James', 'Charlotte', 'Benjamin', 'Lucas', 'Harper', 'Henry', 'Alexander', 'Sebastian', 'Jack', 'Owen']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Martinez', 'Wilson',
              'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Allen', 'King', 'Scott']


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


def make_fingerprint():
    fingerprint = f"ECdITeCs:{base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')[:43]}"
    return fingerprint


def api_execute(url, step_id, workflow_state, inputs, headers):
    """Make an API execute call."""
    payload = {
        "stepId": step_id,
        "workflowStateHandle": workflow_state,
        "inputs": inputs
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    return resp


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
    
    headers = {
        'User-Agent': UAMOBILE,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json',
        'Origin': 'https://us-east-1.signin.aws',
        'Referer': f'https://us-east-1.signin.aws/platform/{DIRECTORY_ID}/login',
    }
    
    base_url = f'https://us-east-1.signin.aws/platform/{DIRECTORY_ID}/api/execute'
    
    # Step 1: Initial load
    print("[1] Initial load...")
    fp = make_fingerprint()
    resp = api_execute(base_url, "", str(uuid.uuid4()), 
                       [{"input_type": "FingerPrintRequestInput", "fingerPrint": fp}], headers)
    data = resp.json()
    state = data.get('workflowStateHandle', '')
    step = data.get('stepId', '')
    print(f"    step={step}, state={state[:20]}...")
    assert resp.status_code == 200, f"Failed: {resp.status_code}"
    
    # Step 2: get-identity-user
    print("[2] Get identity user (email form)...")
    resp = api_execute(base_url, step, state,
                       [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()}], headers)
    data = resp.json()
    state = data.get('workflowStateHandle', '')
    step = data.get('stepId', '')
    print(f"    step={step}, state={state[:20]}...")
    assert resp.status_code == 200
    
    # Step 3: Submit email
    print(f"[3] Submit email: {email}")
    resp = api_execute(base_url, step, state,
                       [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()},
                        {"input_type": "TextInput", "key": "identity", "value": email}], headers)
    data = resp.json()
    state = data.get('workflowStateHandle', '')
    step = data.get('stepId', '')
    msg = data.get('message', {})
    error = msg.get('errorCode', '') if isinstance(msg, dict) else ''
    print(f"    step={step}, state={state[:20]}... error={error}")
    assert resp.status_code == 200
    
    # Step 4: get-verified-username (name form) - on profile.aws.amazon.com
    print("[4] Name form...")
    profile_headers = {
        'User-Agent': UAMOBILE,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json',
        'Origin': 'https://profile.aws.amazon.com',
        'Referer': 'https://profile.aws.amazon.com/',
    }
    profile_url = 'https://profile.aws.amazon.com/api/execute'
    
    # The redirect might need a different workflow
    # Try continuing on the same endpoint first
    resp = api_execute(base_url, step, state,
                       [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()}], headers)
    data = resp.json()
    state = data.get('workflowStateHandle', '')
    step = data.get('stepId', '')
    print(f"    step={step}, state={state[:20]}...")
    
    # If step is now on profile.aws.amazon.com, switch
    if 'profile' in data.get('redirectUri', '') or 'profile' in str(data.get('message', '')):
        print("    Redirecting to profile.aws.amazon.com...")
        # Start new workflow on profile
        resp = api_execute(profile_url, "", str(uuid.uuid4()),
                           [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()}], profile_headers)
        data = resp.json()
        state = data.get('workflowStateHandle', '')
        step = data.get('stepId', '')
        print(f"    Profile: step={step}, state={state[:20]}...")
    
    # Step 5: Submit name
    print(f"[5] Submit name: {full_name}")
    resp = api_execute(profile_url, step, state,
                       [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()},
                        {"input_type": "TextInput", "key": "verifiedUserName", "value": full_name}], profile_headers)
    data = resp.json()
    state = data.get('workflowStateHandle', '')
    step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '') if isinstance(data.get('message'), dict) else ''
    print(f"    step={step}, state={state[:20]}... error={error}")
    
    # Step 6: send-otp
    print("[6] Send OTP...")
    resp = api_execute(profile_url, step, state,
                       [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()}], profile_headers)
    data = resp.json()
    state = data.get('workflowStateHandle', '')
    step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '') if isinstance(data.get('message'), dict) else ''
    print(f"    step={step}, state={state[:20]}... error={error}")
    
    # Step 7: Get OTP from Gmail
    print("[7] Fetching OTP...")
    otp = None
    for i in range(30):
        otp = extract_otp()
        if otp:
            break
        time.sleep(3)
    
    if not otp:
        print("    [!] No OTP received!")
        return
    
    print(f"    OTP: {otp}")
    
    # Step 8: Submit OTP
    print("[8] Submit OTP...")
    resp = api_execute(profile_url, step, state,
                       [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()},
                        {"input_type": "TextInput", "key": "otp", "value": otp}], profile_headers)
    data = resp.json()
    state = data.get('workflowStateHandle', '')
    step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '') if isinstance(data.get('message'), dict) else ''
    print(f"    step={step}, state={state[:20]}... error={error}")
    
    # Step 9: Set password
    print("[9] Set password...")
    resp = api_execute(profile_url, step, state,
                       [{"input_type": "FingerPrintRequestInput", "fingerPrint": make_fingerprint()},
                        {"input_type": "PasswordInput", "key": "password", "value": password},
                        {"input_type": "PasswordInput", "key": "confirmPassword", "value": password}], profile_headers)
    data = resp.json()
    state = data.get('workflowStateHandle', '')
    step = data.get('stepId', '')
    error = data.get('message', {}).get('errorCode', '') if isinstance(data.get('message'), dict) else ''
    print(f"    step={step}, state={state[:20]}... error={error}")
    
    print("\n[FINAL] API flow complete!")
    print(f"    Email: {email}")
    print(f"    Password: {password}")
    print(f"    Final step: {step}")
    
    # Save result
    with open('/home/ubuntu/kiro-gen/api_flow_result.json', 'w') as f:
        json.dump({'email': email, 'password': password, 'name': full_name, 'final_step': step,
                   'final_state': state}, f, indent=2)
    print("    Result saved to api_flow_result.json")


if __name__ == '__main__':
    main()
