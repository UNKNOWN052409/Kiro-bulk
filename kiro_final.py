#!/usr/bin/env python3
"""
Kiro AI Account Creator - Browser + page.request API Calls
Strategy:
1. Browser navigates through proxy to get workflow state (OIDC flow)
2. All API calls use page.request.post() which shares the browser's connection pool
3. This avoids the CONNECTION_ISSUE by reusing the same TLS connections
"""

import uuid, secrets, hashlib, base64, time, random, re, json, sys
from urllib.parse import quote, urlparse, parse_qs
import subprocess
import socket
import imaplib
import requests as req
import email as email_lib
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

CALLBACK_PORT = 9997
HTTP_PROXY_PORT = 8899
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_PASS = 'hlcv eobi tfwh terw'
DIRECTORY_ID = 'd-9067642ac7'
SIGNIN_BASE = f'https://us-east-1.signin.aws/platform/{DIRECTORY_ID}'
API_URL = f'{SIGNIN_BASE}/api/execute'

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'James', 'Charlotte', 'Benjamin', 'Lucas', 'Harper', 'Henry', 'Alexander', 'Sebastian', 'Jack', 'Owen']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Martinez', 'Wilson',
              'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Allen', 'King', 'Scott']

CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'


def extract_otp():
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select('inbox')
        status, messages = mail.search(None, '(FROM "amazon")')
        if status != 'OK' or not messages[0]:
            mail.logout()
            return None
        msg_ids = messages[0].split()
        for msg_id in reversed(msg_ids[-10:]):
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            if 'amazon' not in msg.get('From', '').lower():
                continue
            otp = None
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() in ('text/plain', 'text/html'):
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        if 'html' in part.get_content_type():
                            body = re.sub(r'<[^>]+>', ' ', body)
                        m = re.search(r'\b(\d{6})\b', body)
                        if m:
                            otp = m.group(1)
                            break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                m = re.search(r'\b(\d{6})\b', body)
                if m:
                    otp = m.group(1)
            if otp:
                mail.logout()
                return otp
        mail.logout()
        return None
    except Exception as e:
        print(f"    [Gmail] {e}")
        return None


def ensure_proxies():
    def is_port_responsive(port):
        try:
            r = req.get('https://api.ipify.org?format=json',
                        proxies={'https': f'http://127.0.0.1:{port}'}, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    try:
        subprocess.run(['pkill', '-f', 'proxy_socks5_wrapper'], capture_output=True)
    except Exception:
        pass
    time.sleep(1)

    subprocess.Popen(
        [sys.executable, '/home/ubuntu/kiro-gen/proxy_socks5_wrapper.py',
         '--port', str(HTTP_PROXY_PORT), '--session', 'res-us'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    for i in range(10):
        time.sleep(1)
        if is_port_responsive(HTTP_PROXY_PORT):
            print(f"  Proxies ready (HTTP:{HTTP_PROXY_PORT})")
            return
    print(f"  Warning: proxy may not be fully ready")


def make_fingerprint():
    return f"ECdITeCs:{base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')[:43]}"


def create_account():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    email_prefix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email_addr = f'{email_prefix}@havenhaus.in'
    password = f'Kiro{email_prefix}!2026'

    account_info = {
        'email': email_addr,
        'name': f'{first_name} {last_name}',
        'password': password,
        'token': '',
        'status': 'pending'
    }

    print(f"\n{'='*60}\nCreating: {first_name} {last_name} <{email_addr}>\n{'='*60}")

    ensure_proxies()

    try:
        # Step 1: OIDC client registration (via curl_cffi - doesn't need browser)
        print("[1] Registering OIDC client...")
        from curl_cffi import requests as cffi
        reg = cffi.post('https://oidc.us-east-1.amazonaws.com/client/register',
                        proxy=f'http://127.0.0.1:{HTTP_PROXY_PORT}',
                        json={
                            'clientName': f'kiro-{uuid.uuid4().hex[:8]}',
                            'clientType': 'public',
                            'scopes': ['codewhisperer:completions', 'codewhisperer:analysis', 'codewhisperer:conversations'],
                            'grantTypes': ['authorization_code', 'refresh_token'],
                            'redirectUris': [f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'],
                            'issuerUrl': 'https://view.awsapps.com/start'
                        })
        client_id = reg.json()['clientId']
        print(f"    Client ID: {client_id}")

        # Step 2: PKCE
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b'=').decode()

        auth_url = (f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code'
                    f'&client_id={client_id}'
                    f'&redirect_uri={quote(f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback")}'
                    f'&scopes=codewhisperer%3Acompletions%20codewhisperer%3Aanalysis%20codewhisperer%3Aconversations'
                    f'&state={secrets.token_urlsafe(16)}'
                    f'&code_challenge={code_challenge}'
                    f'&code_challenge_method=S256')

        # Step 3: Browser
        print("[2] Browser: navigate to authorize URL...")
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                '/tmp/chrome-profile-final',
                channel='chromium',
                headless=True,
                viewport={'width': 1920, 'height': 1080},
                user_agent=CHROME_UA,
                locale='en-US',
                timezone_id='America/New_York',
                proxy={'server': f'http://127.0.0.1:{HTTP_PROXY_PORT}'},
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled'],
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Navigate to OIDC authorize URL
            page.goto(auth_url, wait_until='load', timeout=120000)
            print(f"    URL after load: {page.url[:120]}")

            # Wait for JS redirect to signin.aws
            ws_handle = None
            try:
                page.wait_for_url('**signin.aws**workflowStateHandle**', timeout=90000)
            except Exception:
                for i in range(60):
                    time.sleep(1)
                    url = page.url
                    if 'signin.aws' in url and 'workflowStateHandle' in url:
                        break

            ws_match = re.search(r'workflowStateHandle=([a-f0-9-]{36})', page.url)
            if ws_match:
                ws_handle = ws_match.group(1)
            if not ws_handle:
                print(f"    [!] No workflow state. URL: {page.url[:120]}")
                account_info['status'] = 'failed_authorize'
                context.close()
                return account_info
            print(f"    WorkflowStateHandle: {ws_handle}")
            time.sleep(3)

            # ALL API calls use page.request.post() - shares browser's connection pool
            current_step = ''
            FP = make_fingerprint()

            def api_call(step_id, ws, inputs=None, action_id='SUBMIT'):
                payload = {
                    'stepId': step_id,
                    'workflowStateHandle': ws,
                    'actionId': action_id,
                    'inputs': inputs or [],
                    'visitorId': str(uuid.uuid4()),
                    'requestId': str(uuid.uuid4()),
                }
                resp = page.request.post(API_URL, data=json.dumps(payload),
                                         headers={'Content-Type': 'application/json'})
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                return {
                    'status': resp.status,
                    'data': data,
                    'ws': data.get('workflowStateHandle', ws),
                    'step': data.get('stepId', ''),
                    'actions': data.get('actionIdList', []),
                    'redirect': data.get('redirect', {}).get('url', ''),
                }

            # Step 4: Init
            print("[3] Init call (signin)...")
            result = api_call('', ws_handle, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP}])
            print(f"    Init: HTTP {result['status']}")
            if result['status'] != 200:
                print(f"    Init: {json.dumps(result.get('data', {}))[:300]}")
                account_info['status'] = 'failed_init'
                context.close()
                return account_info

            ws_handle = result.get('ws', ws_handle)
            current_step = result.get('step', '')
            print(f"    Init: step={current_step}, ws={ws_handle[:20]}...")
            time.sleep(random.uniform(3, 5))

            # Step 4a: Load email form
            print(f"[4a] Loading email form...")
            result = api_call(current_step, ws_handle, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP}])
            print(f"    Load email form: HTTP {result['status']}")
            if result['status'] != 200:
                print(f"    Load email form: {json.dumps(result.get('data', {}))[:300]}")
                account_info['status'] = 'failed_email_form'
                context.close()
                return account_info

            ws_handle = result.get('ws', ws_handle)
            current_step = result.get('step', current_step)
            print(f"    Load email form: step={current_step}")
            print(f"    Available actions: {result.get('actions', [])}")
            time.sleep(random.uniform(3, 5))

            # Step 4b: Submit email
            print(f"[4b] Submit email: {email_addr}")
            result = api_call(current_step, ws_handle, [
                {'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP},
                {'input_type': 'UserRequestInput', 'identity': email_addr},
            ], action_id='SIGNUP')

            if result['status'] != 200:
                print(f"    SIGNUP failed, trying SUBMIT...")
                result = api_call(current_step, ws_handle, [
                    {'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP},
                    {'input_type': 'UserRequestInput', 'identity': email_addr},
                ], action_id='SUBMIT')

            print(f"    Email: HTTP {result['status']}")
            if result['status'] != 200:
                print(f"    Email: {json.dumps(result.get('data', {}))[:300]}")
                account_info['status'] = 'failed_email'
                context.close()
                return account_info

            ws_handle = result.get('ws', ws_handle)
            current_step = result.get('step', current_step)
            print(f"    Email: step={current_step}")

            redirect_url = result.get('redirect', '')
            if redirect_url:
                ws_match = re.search(r'workflowStateHandle=([a-f0-9-]{36})', redirect_url)
                if ws_match:
                    ws_handle = ws_match.group(1)
                    print(f"    Got WS from redirect: {ws_handle[:20]}...")
            print(f"    Redirect URL: {redirect_url[:100]}")
            time.sleep(random.uniform(3, 5))

            # Step 5: Navigate to signup page then submit name
            print(f"[5] Navigating to signup page...")
            full_name = f'{first_name} {last_name}'
            
            # Navigate to the signup page
            signup_url = redirect_url if redirect_url.startswith('http') else f'https://us-east-1.signin.aws/platform/d-9067642ac7{redirect_url}'
            print(f"    Navigating to: {signup_url[:120]}")
            page.goto(signup_url, wait_until='load', timeout=60000)
            print(f"    On: {page.url[:100]}")
            time.sleep(5)
            
            # The signup API is at /signup/api/execute
            SIGNUP_API_URL = 'https://us-east-1.signin.aws/platform/d-9067642ac7/signup/api/execute'
            
            # Use WS from the redirect URL
            ws_from_redirect = re.search(r'workflowStateHandle=([a-f0-9-]{36})', redirect_url)
            ws_r = ws_from_redirect.group(1) if ws_from_redirect else ws_handle
            print(f"    WS from redirect: {ws_r}")
            
            def signup_api_call(step_id, ws, inputs=None, action_id='SUBMIT'):
                payload = {
                    'stepId': step_id,
                    'workflowStateHandle': ws,
                    'actionId': action_id,
                    'inputs': inputs or [],
                    'visitorId': str(uuid.uuid4()),
                    'requestId': str(uuid.uuid4()),
                }
                resp = page.request.post(SIGNUP_API_URL, data=json.dumps(payload),
                                         headers={'Content-Type': 'application/json'})
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                return {
                    'status': resp.status,
                    'data': data,
                    'ws': data.get('workflowStateHandle', ws),
                    'step': data.get('stepId', ''),
                    'actions': data.get('actionIdList', []),
                    'redirect': data.get('redirect', {}).get('url', ''),
                }
            
            # Attempt: use WS from redirect, step='user-signup'
            print(f"    Attempt 1: WS from redirect, step=user-signup")
            result = signup_api_call('user-signup', ws_r, [
                {'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP},
                {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': full_name},
            ], action_id='SUBMIT')
            print(f"    Name submit: HTTP {result['status']}")
            name_ok = result['status'] == 200
            
            if not name_ok:
                print(f"    Attempt 2: Init on signup API, then name submit")
                r = signup_api_call('', ws_r, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP}])
                print(f"    SignupInit: HTTP {r['status']}, step={r['step']}")
                if r['status'] == 200:
                    time.sleep(2)
                    result = signup_api_call(r['step'], r['ws'], [
                        {'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP},
                        {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': full_name},
                    ], action_id='SUBMIT')
                    print(f"    Name submit: HTTP {result['status']}")
                    name_ok = result['status'] == 200

            if not name_ok:
                print(f"    [!] Name submission failed: {json.dumps(result.get('data', {}))[:300]}")
                account_info['status'] = 'failed_name'
                context.close()
                return account_info

            ws_handle = result.get('ws', ws_handle)
            current_step = result.get('step', current_step)
            print(f"    Name: step={current_step}, ws={ws_handle[:20]}...")
            time.sleep(random.uniform(3, 5))

            # Step 6: Send OTP
            print("[6] Send OTP...")
            result = signup_api_call(current_step, ws_handle,
                              [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP}])
            print(f"    OTP send: HTTP {result['status']}")
            if result['status'] != 200:
                print(f"    OTP send: {json.dumps(result.get('data', {}))[:300]}")
                account_info['status'] = 'failed_otp_send'
                context.close()
                return account_info

            ws_handle = result.get('ws', ws_handle)
            current_step = result.get('step', current_step)
            print(f"    OTP send: step={current_step}")
            time.sleep(random.uniform(3, 5))

            # Step 7: Wait for OTP
            print("[7] Waiting for OTP email...")
            otp = None
            for attempt in range(15):
                otp = extract_otp()
                if otp:
                    break
                time.sleep(10)

            if not otp:
                print("    [!] OTP not received")
                account_info['status'] = 'failed_otp'
                context.close()
                return account_info
            print(f"    OTP received: {otp}")
            time.sleep(2)

            # Step 8: Submit OTP
            print("[8] Submit OTP...")
            result = signup_api_call(current_step, ws_handle, [
                {'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP},
                {'input_type': 'TextInput', 'key': 'otp', 'value': otp},
            ], action_id='SUBMIT')

            print(f"    OTP submit: HTTP {result['status']}")
            if result['status'] != 200:
                print(f"    OTP submit: {json.dumps(result.get('data', {}))[:300]}")
                account_info['status'] = 'failed_otp_verify'
                context.close()
                return account_info

            ws_handle = result.get('ws', ws_handle)
            current_step = result.get('step', current_step)
            print(f"    OTP verify: step={current_step}")
            time.sleep(random.uniform(3, 5))

            # Step 9: Set password
            print("[9] Setting password...")
            result = signup_api_call(current_step, ws_handle, [
                {'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP},
                {'input_type': 'PasswordInput', 'key': 'password', 'value': password},
            ], action_id='SUBMIT')

            print(f"    Password: HTTP {result['status']}")
            if result['status'] != 200:
                print(f"    Password: {json.dumps(result.get('data', {}))[:300]}")
                account_info['status'] = 'failed_password'
                context.close()
                return account_info

            ws_handle = result.get('ws', ws_handle)
            current_step = result.get('step', current_step)
            print(f"    Password: step={current_step}")

            # Check completion
            data = result.get('data', {})
            if 'token' in data or 'idToken' in data or 'accessToken' in data:
                token = data.get('token') or data.get('idToken') or data.get('accessToken')
                account_info['token'] = token
                account_info['status'] = 'success'
                print(f"    SUCCESS! Token: {token[:50]}...")
            else:
                auth_code = data.get('code') or data.get('authorizationCode')
                if auth_code:
                    print(f"    Got auth code: {auth_code[:20]}...")
                    token_resp = cffi.post(
                        'https://oidc.us-east-1.amazonaws.com/token',
                        proxy=f'http://127.0.0.1:{HTTP_PROXY_PORT}',
                        json={
                            'client_id': client_id,
                            'grant_type': 'authorization_code',
                            'code': auth_code,
                            'redirect_uri': f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback',
                            'code_verifier': code_verifier,
                        }
                    )
                    if token_resp.status_code == 200:
                        token_data = token_resp.json()
                        account_info['token'] = token_data.get('id_token', token_data.get('access_token', ''))
                        account_info['status'] = 'success'
                        print(f"    SUCCESS! Token obtained.")
                    else:
                        account_info['status'] = 'success_no_token'
                        print(f"    Account created but token exchange failed")
                else:
                    account_info['status'] = 'success_pending'
                    print(f"    Account created. Final: {json.dumps(data)[:300]}")

            context.close()

    except Exception as e:
        print(f"    [ERROR] {e}")
        import traceback
        traceback.print_exc()
        account_info['status'] = f'error: {str(e)[:100]}'

    return account_info


def main():
    result = create_account()
    print(f"\n{'='*60}\nResult: {json.dumps(result, indent=2)}\n{'='*60}")
    with open('/home/ubuntu/kiro-gen/last_account.json', 'w') as f:
        json.dump(result, f, indent=2)
    print("Saved to last_account.json")


if __name__ == '__main__':
    main()
