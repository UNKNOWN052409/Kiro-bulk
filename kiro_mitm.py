#!/usr/bin/env python3
"""
Kiro AI Account Creator - MITM Style (No Browser)
Uses curl_cffi to impersonate Chrome TLS fingerprint through SOCKS5 residential proxy.
Replays the exact API calls from the OIDC signin flow.
"""

import uuid, secrets, hashlib, base64, time, random, re, json, sys
from urllib.parse import quote, urlparse, parse_qs
from curl_cffi import requests as cffi_requests
import imaplib
import email as email_lib
import email.utils
from datetime import datetime, timezone

# Configuration
CALLBACK_PORT = 9997
SOCKS5_PORT = 10800
HTTP_PROXY_PORT = 8899

GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_PASS = 'hlcv eobi tfwh terw'

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'James', 'Charlotte', 'Benjamin', 'Lucas', 'Harper', 'Henry', 'Alexander', 'Sebastian', 'Jack', 'Owen',
               'Daniel', 'Matthew', 'Anthony', 'Mark', 'Donald', 'Steven', 'Andrew', 'Paul', 'Joshua', 'Kenneth',
               'Kevin', 'Brian', 'George', 'Timothy', 'Ronald', 'Edward', 'Jason', 'Jeffrey', 'Ryan', 'Jacob']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Martinez', 'Wilson',
              'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Allen', 'King', 'Scott',
              'Wright', 'Lopez', 'Hill', 'Green', 'Adams', 'Baker', 'Gonzalez', 'Nelson', 'Carter', 'Mitchell']

CHROME_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Content-Type': 'application/json',
    'Origin': 'https://us-east-1.signin.aws',
    'Referer': 'https://us-east-1.signin.aws/platform/d-9067642ac7/login',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}


def create_session():
    return cffi_requests.Session(
        impersonate='chrome124',
        proxy=f'http://127.0.0.1:{HTTP_PROXY_PORT}',
        timeout=60,
    )


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
            from_addr = msg.get('From', '')
            if 'amazon' not in from_addr.lower():
                continue
            
            try:
                msg_date = email.utils.parsedate_to_datetime(msg.get('Date', ''))
                age = (datetime.now(timezone.utc) - msg_date).total_seconds() if msg_date.tzinfo else 0
                if age > 300:
                    continue
            except:
                pass
            
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
        print(f"    [Gmail] Error: {e}")
        return None


def create_account():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email_addr = f'{random_suffix}@havenhaus.in'
    password = f'Kiro{random_suffix[:4]}!2026'
    
    account_info = {
        'email': email_addr,
        'name': full_name,
        'password': password,
        'status': 'pending'
    }
    
    print(f"\n{'='*60}")
    print(f"Creating: {full_name} <{email_addr}>")
    print(f"Password: {password}")
    print(f"{'='*60}\n")
    
    session = create_session()
    
    try:
        # Step 1: Register OIDC client
        print("[1] Registering OIDC client...")
        reg_data = {
            'clientName': f'kiro-{uuid.uuid4().hex[:8]}',
            'clientType': 'public',
            'scopes': ['codewhisperer:completions', 'codewhisperer:analysis', 'codewhisperer:conversations'],
            'grantTypes': ['authorization_code', 'refresh_token'],
            'redirectUris': [f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'],
            'issuerUrl': 'https://view.awsapps.com/start'
        }
        reg_resp = session.post('https://oidc.us-east-1.amazonaws.com/client/register', json=reg_data)
        if reg_resp.status_code != 200:
            print(f"    [!] Register failed: {reg_resp.status_code}")
            account_info['status'] = 'failed_register'
            return account_info
        
        client_id = reg_resp.json()['clientId']
        print(f"    Client ID: {client_id}")
        
        # Step 2: PKCE
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b'=').decode()
        
        # Step 3: OIDC Authorize - follow ALL redirects to get to the final login page
        print("[2] OIDC Authorize (following redirects)...")
        state = secrets.token_urlsafe(16)
        scopes = 'codewhisperer:completions codewhisperer:analysis codewhisperer:conversations'
        auth_url = (f'https://oidc.us-east-1.amazonaws.com/authorize'
                    f'?response_type=code'
                    f'&client_id={client_id}'
                    f'&redirect_uri={quote(f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback")}'
                    f'&scopes={quote(scopes)}'
                    f'&state={state}'
                    f'&code_challenge={code_challenge}'
                    f'&code_challenge_method=S256')
        
        # Follow redirects manually to capture intermediate URLs
        current_url = auth_url
        workflow_state = None
        directory_id = None
        
        for i in range(10):
            # Parse current URL to check if it's a localhost redirect
            parsed_current = urlparse(current_url)
            is_localhost = parsed_current.netloc.startswith('127.0.0.1') or 'localhost' in parsed_current.netloc
            
            if is_localhost:
                print(f"    [{i}] Reached localhost callback: {current_url[:120]}")
                # Parse the callback URL for error or code
                params = parse_qs(parsed_current.query)
                if 'error' in params:
                    print(f"    [!] OAuth error: {params['error'][0]} - {params.get('error_description', [''])[0]}")
                if 'code' in params:
                    oauth_code = params['code'][0]
                    print(f"    OAuth code found in callback: {oauth_code[:20]}...")
                    break
                break
            
            resp = session.get(current_url, allow_redirects=False)
            status = resp.status_code
            
            if status == 200:
                # We've reached the final page
                html = resp.text
                # Extract workflow state from HTML
                ws_match = re.search(r'workflowStateHandle["\s:=\'\"]+([a-f0-9-]{36})', html)
                if ws_match:
                    workflow_state = ws_match.group(1)
                dir_match = re.search(r'platform/d-([a-f0-9]+)/', current_url)
                if dir_match:
                    directory_id = dir_match.group(1)
                print(f"    Final page: {current_url[:80]}")
                print(f"    Workflow: {workflow_state}")
                print(f"    Directory: d-{directory_id}")
                
                # If no workflow state yet, try to navigate to the signin platform directly
                if not workflow_state or not directory_id:
                    # The start page is a SPA - it loads the login page via JavaScript
                    # Try to get the signin platform page directly
                    print("    Trying signin platform directly...")
                    signin_url = 'https://us-east-1.signin.aws/platform/d-9067642ac7/login'
                    signin_resp = session.get(signin_url, allow_redirects=False, headers=CHROME_HEADERS)
                    print(f"    Signin status: {signin_resp.status_code}")
                    
                    if signin_resp.status_code in (301, 302, 303, 307, 308):
                        loc = signin_resp.headers.get('Location', '')
                        print(f"    Signin redirect: {loc[:100]}")
                        # Extract workflow from redirect URL
                        ws_url = re.search(r'workflowStateHandle=([a-f0-9-]{36})', loc)
                        if ws_url:
                            workflow_state = ws_url.group(1)
                        dir_url = re.search(r'platform/d-([a-f0-9]+)/', loc)
                        if dir_url:
                            directory_id = dir_url.group(1)
                        current_url = loc
                    elif signin_resp.status_code == 200:
                        # Check for workflow state in the signin page HTML
                        ws_html = re.search(r'workflowStateHandle["\s:=\'\"]+([a-f0-9-]{36})', signin_resp.text)
                        if ws_html:
                            workflow_state = ws_html.group(1)
                        dir_html = re.search(r'platform/d-([a-f0-9]+)/', signin_url)
                        if dir_html:
                            directory_id = dir_html.group(1)
                        print(f"    From signin page - Workflow: {workflow_state}, Dir: d-{directory_id}")
                
                if workflow_state and directory_id:
                    break
                else:
                    print(f"    [!] Still no workflow state - breaking")
                    break
            elif status in (301, 302, 303, 307, 308):
                location = resp.headers.get('Location', '')
                # Check for workflow state in URL
                ws_url_match = re.search(r'workflowStateHandle=([a-f0-9-]{36})', location)
                if ws_url_match and not workflow_state:
                    workflow_state = ws_url_match.group(1)
                dir_url_match = re.search(r'platform/d-([a-f0-9]+)/', location)
                if dir_url_match and not directory_id:
                    directory_id = dir_url_match.group(1)
                print(f"    [{i}] {status} -> {location[:80]}")
                current_url = location
                time.sleep(0.3)
            else:
                print(f"    [{i}] Unexpected status: {status}")
                break
        
        if not workflow_state or not directory_id:
            print(f"    [!] Could not extract workflow state or directory")
            # Try to get from the view.awsapps.com/start page
            print(f"    Current URL: {current_url}")
            account_info['status'] = 'failed_authorize'
            return account_info
        
        # Step 4: Execute email step
        print("[3] Submitting email...")
        email_payload = {
            'workflowStateHandle': workflow_state,
            'stepId': 'get-identity-user',
            'input': {'username': email_addr}
        }
        exec_resp = session.post(
            f'https://us-east-1.signin.aws/platform/d-{directory_id}/api/execute',
            json=email_payload,
            headers=API_HEADERS
        )
        print(f"    Email status: {exec_resp.status_code}")
        if exec_resp.status_code != 200:
            print(f"    Body: {exec_resp.text[:300]}")
            account_info['status'] = 'failed_email'
            return account_info
        
        email_result = exec_resp.json()
        print(f"    Result: {json.dumps(email_result)[:200]}")
        
        # Extract new workflow state if updated
        new_ws = email_result.get('workflowStateHandle', workflow_state)
        if new_ws:
            workflow_state = new_ws
        
        # Step 5: Submit name
        print("[4] Submitting name...")
        time.sleep(random.uniform(2, 4))
        name_payload = {
            'workflowStateHandle': workflow_state,
            'stepId': 'set-user-attributes',
            'input': {'attributes': {'name': full_name}}
        }
        name_resp = session.post(
            f'https://us-east-1.signin.aws/platform/d-{directory_id}/api/execute',
            json=name_payload,
            headers=API_HEADERS
        )
        print(f"    Name status: {name_resp.status_code}")
        if name_resp.status_code != 200:
            print(f"    Body: {name_resp.text[:300]}")
            account_info['status'] = 'failed_name'
            return account_info
        
        name_result = name_resp.json()
        print(f"    Result: {json.dumps(name_result)[:200]}")
        new_ws = name_result.get('workflowStateHandle', workflow_state)
        if new_ws:
            workflow_state = new_ws
        
        # Step 6: Send OTP
        print("[5] Sending OTP...")
        time.sleep(random.uniform(2, 4))
        otp_payload = {
            'workflowStateHandle': workflow_state,
            'stepId': 'send-otp',
            'input': {}
        }
        otp_resp = session.post(
            f'https://us-east-1.signin.aws/platform/d-{directory_id}/api/execute',
            json=otp_payload,
            headers=API_HEADERS
        )
        print(f"    OTP send status: {otp_resp.status_code}")
        if otp_resp.status_code != 200:
            print(f"    Body: {otp_resp.text[:300]}")
            if 'BLOCKED' in otp_resp.text or 'TES' in otp_resp.text:
                account_info['status'] = 'failed_tes'
            else:
                account_info['status'] = 'failed_otp_send'
            return account_info
        
        otp_result = otp_resp.json()
        print(f"    OTP result: {json.dumps(otp_result)[:200]}")
        new_ws = otp_result.get('workflowStateHandle', workflow_state)
        if new_ws:
            workflow_state = new_ws
        
        # Step 7: Get OTP
        print("[6] Waiting for OTP email...")
        otp_code = None
        for i in range(20):
            otp_code = extract_otp()
            if otp_code:
                break
            print(f"    Waiting... ({i+1}/20)")
            time.sleep(5)
        
        if not otp_code:
            print("    [!] OTP not received")
            account_info['status'] = 'failed_otp_extract'
            return account_info
        
        print(f"    OTP: {otp_code}")
        
        # Step 8: Submit OTP
        print("[7] Submitting OTP...")
        time.sleep(random.uniform(1, 3))
        otp_verify_payload = {
            'workflowStateHandle': workflow_state,
            'stepId': 'verify-otp',
            'input': {'otp': otp_code}
        }
        verify_resp = session.post(
            f'https://us-east-1.signin.aws/platform/d-{directory_id}/api/execute',
            json=otp_verify_payload,
            headers=API_HEADERS
        )
        print(f"    OTP verify status: {verify_resp.status_code}")
        if verify_resp.status_code != 200:
            print(f"    Body: {verify_resp.text[:300]}")
            account_info['status'] = 'failed_otp_verify'
            return account_info
        
        verify_result = verify_resp.json()
        print(f"    Verify result: {json.dumps(verify_result)[:200]}")
        new_ws = verify_result.get('workflowStateHandle', workflow_state)
        if new_ws:
            workflow_state = new_ws
        
        # Step 9: Set password
        print("[8] Setting password...")
        time.sleep(random.uniform(1, 3))
        pw_payload = {
            'workflowStateHandle': workflow_state,
            'stepId': 'set-password',
            'input': {'password': password}
        }
        pw_resp = session.post(
            f'https://us-east-1.signin.aws/platform/d-{directory_id}/api/execute',
            json=pw_payload,
            headers=API_HEADERS
        )
        print(f"    Password status: {pw_resp.status_code}")
        if pw_resp.status_code != 200:
            print(f"    Body: {pw_resp.text[:300]}")
            account_info['status'] = 'failed_password'
            return account_info
        
        pw_result = pw_resp.json()
        print(f"    Password result: {json.dumps(pw_result)[:300]}")
        
        # Step 10: Extract OAuth code
        oauth_code = None
        
        # Check response body for code
        code_match = re.search(r'code=([A-Za-z0-9._~\-]+)', json.dumps(pw_result))
        if code_match:
            oauth_code = code_match.group(1)
        
        # Check headers
        if not oauth_code and 'Location' in pw_resp.headers:
            code_match = re.search(r'code=([A-Za-z0-9._~\-]+)', pw_resp.headers['Location'])
            if code_match:
                oauth_code = code_match.group(1)
        
        # Check redirectUri field
        if not oauth_code:
            redirect_uri = pw_result.get('redirectUri', pw_result.get('location', ''))
            if 'code=' in str(redirect_uri):
                code_match = re.search(r'code=([A-Za-z0-9._~\-]+)', redirect_uri)
                if code_match:
                    oauth_code = code_match.group(1)
        
        if not oauth_code:
            print(f"    [!] No OAuth code found")
            print(f"    Full response keys: {list(pw_result.keys())}")
            print(f"    Response: {json.dumps(pw_result)[:500]}")
            account_info['status'] = 'no_oauth_code'
            return account_info
        
        print(f"    OAuth code: {oauth_code[:30]}...")
        account_info['oauth_code'] = oauth_code
        account_info['code_verifier'] = code_verifier
        account_info['client_id'] = client_id
        account_info['status'] = 'success'
        
        # Step 11: Exchange code for token
        print("[9] Exchanging code for token...")
        token_resp = session.post('https://oidc.us-east-1.amazonaws.com/token', json={
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'code': oauth_code,
            'redirect_uri': f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback',
            'code_verifier': code_verifier
        })
        print(f"    Token status: {token_resp.status_code}")
        if token_resp.status_code == 200:
            token_data = token_resp.json()
            account_info['access_token'] = token_data.get('access_token', '')
            account_info['refresh_token'] = token_data.get('refresh_token', '')
            account_info['id_token'] = token_data.get('id_token', '')
            print(f"    ✓ Token captured!")
        else:
            print(f"    [!] Token exchange failed: {token_resp.text[:300]}")
            account_info['status'] = 'partial'
        
    except Exception as e:
        print(f"    [!] Exception: {e}")
        import traceback
        traceback.print_exc()
        account_info['status'] = 'failed_exception'
    
    session.close()
    return account_info


if __name__ == '__main__':
    result = create_account()
    print(f"\n{'='*60}")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"{'='*60}")
    
    with open('/home/ubuntu/kiro-gen/last_account.json', 'w') as f:
        json.dump(result, f, indent=2)
    print("Saved to last_account.json")
