#!/usr/bin/env python3
"""
Complete API-only account creation.
No browser needed - pure HTTP requests through residential proxy.

Flow:
1. Register OIDC client (no proxy)
2. Get workflowStateHandle via redirect chain (proxy)
3. Submit email via API (proxy)
4. Submit signup via API (proxy)
5. Get profile workflowID from signup response
6. Call profile.aws.amazon.com APIs (proxy)
7. Submit name, OTP, password via API
8. Capture tokens
"""

import uuid
import secrets
import hashlib
import base64
import requests
import random
import string
import json
import time
import re
import sys
import threading
from urllib.parse import quote, urlparse

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = [
    "codewhisperer:completions",
    "codewhisperer:analysis", 
    "codewhisperer:conversations",
    "codewhisperer:transformations",
    "codewhisperer:taskassist"
]

PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'

# Load fingerprints
try:
    with open('/home/ubuntu/kiro-gen/cloak_fingerprint.txt', 'r') as f:
        CLOAK_FP = f.read().strip()
except:
    CLOAK_FP = ""

try:
    with open('/home/ubuntu/kiro-gen/profile_fingerprint.txt', 'r') as f:
        PROFILE_FP = f.read().strip()
except:
    PROFILE_FP = ""

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Sai", "Arjun", "Reyansh", "Krishna", "Ishaan", "Shaurya", "Atharv",
               "Aadhya", "Saanvi", "Ananya", "Diya", "Kiara", "Ira", "Myra", "Sara", "Aanya", "Anvi",
               "Liam", "Noah", "Ethan", "Mason", "Lucas", "Oliver", "Elijah", "James", "William", "Benjamin"]

LAST_NAMES = ["Sharma", "Verma", "Singh", "Patel", "Kumar", "Gupta", "Mehta", "Joshi", "Reddy", "Nair",
              "Rao", "Pillai", "Menon", "Iyer", "Bhat", "Desai", "Shah", "Chopra", "Malhotra", "Khanna"]

GMAIL_EMAIL = "anshika31618@gmail.com"
GMAIL_PASSWORD = "hlcv eobi tfwh terw"


def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def generate_password():
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(random.choices(chars, k=14))

def create_api_session():
    session = requests.Session()
    proxy_url = f"socks5://api-US:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
    session.proxies = {'http': proxy_url, 'https': proxy_url}
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    return session

def create_no_proxy_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    })
    return session

def register_oidc_client():
    reg_payload = {
        "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
        "clientType": "public",
        "scopes": GRANT_SCOPES,
        "grantTypes": ["authorization_code", "refresh_token"],
        "redirectUris": ["http://127.0.0.1:9997/oauth/callback"],
        "issuerUrl": ISSUER_URL
    }
    reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
    return reg_resp.json()

def create_pkce():
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    return code_verifier, code_challenge

def get_workflow_state_handle(session, auth_url):
    """Follow the redirect chain to get workflowStateHandle"""
    current_url = auth_url
    
    for i in range(15):
        try:
            resp = session.get(current_url, allow_redirects=False, timeout=15)
            status = resp.status_code
            
            if status in (301, 302, 303, 307, 308):
                location = resp.headers.get('Location', '')
                if not location:
                    break
                
                if location.startswith('/'):
                    parsed = urlparse(current_url)
                    current_url = f"{parsed.scheme}://{parsed.netloc}{location}"
                else:
                    current_url = location
                
                if 'workflowStateHandle=' in current_url:
                    wsh = current_url.split('workflowStateHandle=')[1].split('&')[0]
                    return wsh, current_url
                    
            elif status == 200:
                if 'workflowStateHandle=' in current_url:
                    wsh = current_url.split('workflowStateHandle=')[1].split('&')[0]
                    return wsh, current_url
                
                if 'workflowStateHandle' in resp.text:
                    match = re.search(r'workflowStateHandle["\']?\s*[:=]\s*["\']?([0-9a-f-]{36})', resp.text)
                    if match:
                        return match.group(1), current_url
                
                # JS redirect from view.awsapps.com to portal.sso
                if 'awsapps.com/start' in current_url and 'orchestrator_id=' in current_url:
                    parts = current_url.split('?')[1]
                    orch_id = None
                    cb_url = None
                    for part in parts.split('&'):
                        if part.startswith('orchestrator_id='):
                            orch_id = part.split('=', 1)[1]
                        elif part.startswith('callback_url='):
                            cb_url = part.split('=', 1)[1]
                    
                    if orch_id:
                        portal_url = f"https://portal.sso.us-east-1.amazonaws.com/login?directory_id=view&orchestrator_id={orch_id}"
                        if cb_url:
                            portal_url += f"&callback_url={cb_url}"
                        current_url = portal_url
                        continue
                
                # portal.sso should redirect to signin.aws
                if 'portal.sso' in current_url:
                    match = re.search(r'window\.location[^=]*=\s*["\']([^"\']+)', resp.text)
                    if match:
                        loc = match.group(1)
                        if loc.startswith('/'):
                            current_url = f"https://portal.sso.us-east-1.amazonaws.com{loc}"
                        else:
                            current_url = loc
                        continue
                    
                    match = re.search(r'<meta[^>]*refresh[^>]*content=["\']\d+;\s*url=([^"\']+)', resp.text, re.I)
                    if match:
                        loc = match.group(1)
                        if loc.startswith('/'):
                            current_url = f"https://portal.sso.us-east-1.amazonaws.com{loc}"
                        else:
                            current_url = loc
                        continue
                
                break
            else:
                break
                
        except Exception as e:
            break
    
    return None, current_url

def api_headers_for(wsh=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://us-east-1.signin.aws',
    }
    if wsh:
        headers['Referer'] = f'https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={wsh}'
    return headers

def api_headers_profile(wid=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://profile.aws.amazon.com',
    }
    if wid:
        headers['Referer'] = f'https://profile.aws.amazon.com/?workflowID={wid}'
    return headers


def create_account():
    """Create a single Kiro AI account via API only"""
    email = generate_email()
    name = generate_name()
    password = generate_password()
    
    result = {
        'email': email,
        'name': name,
        'password': password,
        'status': 'failed',
        'error': None,
        'token': None
    }
    
    try:
        # Step 1: Register OIDC client (no proxy needed)
        client_info = register_oidc_client()
        client_id = client_info['clientId']
        
        # Step 2: Create PKCE
        code_verifier, code_challenge = create_pkce()
        
        # Step 3: Build auth URL
        scopes_encoded = ' '.join(GRANT_SCOPES)
        state = secrets.token_urlsafe(16)
        redirect_uri = 'http://127.0.0.1:9997/oauth/callback'
        auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                    f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
                    f'&state={state}&code_challenge={code_challenge}'
                    f'&code_challenge_method=S256')
        
        # Step 4: Create API session with proxy
        session = create_api_session()
        
        # Step 5: Get workflowStateHandle
        workflow_state_handle, final_url = get_workflow_state_handle(session, auth_url)
        
        if not workflow_state_handle:
            result['error'] = 'Could not get workflowStateHandle'
            return result
        
        # Step 6: Submit email via API
        visitor_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        
        email_payload = {
            "stepId": "get-identity-user",
            "workflowStateHandle": workflow_state_handle,
            "actionId": "SUBMIT",
            "inputs": [
                {"input_type": "UserRequestInput", "username": email},
                {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FP} if CLOAK_FP else {"input_type": "UserRequestInput", "username": email}
            ],
            "visitorId": visitor_id,
            "requestId": request_id
        }
        
        email_resp = session.post(
            f'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute',
            json=email_payload,
            headers=api_headers_for(workflow_state_handle),
            timeout=30
        )
        
        if email_resp.status_code != 200:
            result['error'] = f'Email submit failed: HTTP {email_resp.status_code}'
            return result
        
        # Step 7: Submit signup via API
        request_id2 = str(uuid.uuid4())
        signup_payload = {
            "stepId": "get-identity-user",
            "workflowStateHandle": workflow_state_handle,
            "actionId": "SIGNUP",
            "inputs": [
                {"input_type": "UserRequestInput", "username": email},
                {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FP} if CLOAK_FP else {"input_type": "UserRequestInput", "username": email}
            ],
            "visitorId": visitor_id,
            "requestId": request_id2
        }
        
        signup_resp = session.post(
            f'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute',
            json=signup_payload,
            headers=api_headers_for(workflow_state_handle),
            timeout=30
        )
        
        if signup_resp.status_code != 200:
            result['error'] = f'Signup failed: HTTP {signup_resp.status_code}'
            return result
        
        signup_data = signup_resp.json()
        
        # Step 8: Get profile workflowID from signup response
        workflow_id = None
        workflow_state = None
        
        # Check various response fields
        if 'workflowResponseData' in signup_data:
            wrd = signup_data['workflowResponseData']
            if isinstance(wrd, dict):
                workflow_id = wrd.get('workflowID') or wrd.get('workflowId')
                workflow_state = wrd.get('workflowState') or wrd.get('state')
        
        if not workflow_id:
            # Try to find it in the response
            resp_text = signup_resp.text
            if 'workflowID' in resp_text:
                match = re.search(r'"workflowID"\s*:\s*"([0-9a-f-]{36})"', resp_text)
                if match:
                    workflow_id = match.group(1)
            elif 'workflowState' in resp_text:
                match = re.search(r'"workflowState"\s*:\s*"([0-9a-f-]{36})"', resp_text)
                if match:
                    workflow_state = match.group(1)
        
        if not workflow_id:
            # Try to get it from the continueUrl or presentationContext
            if 'presentationContext' in signup_data:
                pc = signup_data['presentationContext']
                if isinstance(pc, dict):
                    workflow_id = pc.get('workflowID') or pc.get('workflowId')
        
        if not workflow_id:
            # We need to navigate to get the profile workflowID
            # This requires a GET to the signup redirect URL
            # Let's try the signup API endpoint
            signup_api_payload = {
                "stepId": "",
                "workflowStateHandle": workflow_state_handle,
                "inputs": [
                    {"input_type": "UserRequestInput", "username": email},
                    {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FP} if CLOAK_FP else {"input_type": "UserRequestInput", "username": email}
                ],
                "visitorId": visitor_id,
                "requestId": str(uuid.uuid4())
            }
            
            signup_api_resp = session.post(
                f'https://us-east-1.signin.aws/platform/d-9067642ac7/signup/api/execute',
                json=signup_api_payload,
                headers=api_headers_for(workflow_state_handle),
                timeout=30
            )
            
            if signup_api_resp.status_code == 200:
                try:
                    sap_data = signup_api_resp.json()
                    if 'workflowResponseData' in sap_data:
                        wrd = sap_data['workflowResponseData']
                        if isinstance(wrd, dict):
                            workflow_id = wrd.get('workflowID') or wrd.get('workflowId')
                            workflow_state = wrd.get('workflowState') or wrd.get('state')
                except:
                    pass
        
        if not workflow_id:
            result['error'] = 'Could not get profile workflowID'
            result['signup_response'] = signup_data
            return result
        
        # Step 9: Profile API calls
        # get-config
        config_resp = session.post(
            'https://profile.aws.amazon.com/api/get-config',
            json={},
            headers=api_headers_profile(workflow_id),
            timeout=30
        )
        
        # get-app-context
        ctx_resp = session.post(
            'https://profile.aws.amazon.com/api/get-app-context',
            json={"workflowID": workflow_id},
            headers=api_headers_profile(workflow_id),
            timeout=30
        )
        
        # start
        start_payload = {
            "workflowID": workflow_id,
            "browserData": {
                "attributes": {
                    "fingerprint": PROFILE_FP
                },
                "cookies": []
            }
        }
        
        start_resp = session.post(
            'https://profile.aws.amazon.com/api/start',
            json=start_payload,
            headers=api_headers_profile(workflow_id),
            timeout=30
        )
        
        if start_resp.status_code != 200:
            result['error'] = f'Profile start failed: HTTP {start_resp.status_code}'
            result['start_response'] = start_resp.text[:300]
            return result
        
        start_data = start_resp.json()
        workflow_state = start_data.get('workflowState') or start_data.get('state') or workflow_state
        
        if not workflow_state:
            result['error'] = 'Could not get workflowState from profile start'
            result['start_response'] = start_data
            return result
        
        # Step 10: Send OTP
        otp_payload = {
            "workflowState": workflow_state,
            "email": email,
            "browserData": {
                "attributes": {
                    "fingerprint": PROFILE_FP
                },
                "cookies": []
            }
        }
        
        otp_resp = session.post(
            'https://profile.aws.amazon.com/api/send-otp',
            json=otp_payload,
            headers=api_headers_profile(workflow_id),
            timeout=30
        )
        
        if otp_resp.status_code != 200:
            result['error'] = f'Send OTP failed: HTTP {otp_resp.status_code}'
            return result
        
        result['status'] = 'otp_sent'
        result['workflow_id'] = workflow_id
        result['workflow_state'] = workflow_state
        
        print(f"  ✓ OTP sent for {email}")
        print(f"  workflowID: {workflow_id}")
        print(f"  workflowState: {workflow_state}")
        
        # Step 11: Wait for OTP email
        print(f"  Waiting for OTP email...")
        otp_code = wait_for_otp(email)
        
        if not otp_code:
            result['error'] = 'Could not get OTP from Gmail'
            return result
        
        print(f"  ✓ OTP received: {otp_code}")
        
        # Step 12: Submit OTP via API
        # Need to check what the OTP submission endpoint is
        # From MITM, after OTP entry, the flow continues to password entry
        # Let's check the response structure
        
        result['otp'] = otp_code
        result['status'] = 'otp_received'
        
        return result
        
    except Exception as e:
        result['error'] = str(e)
        return result


def wait_for_otp(email, timeout=120):
    """Wait for OTP email from Gmail"""
    import imaplib
    import email as email_lib
    from email.header import decode_header
    
    otp_code = None
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
            mail.select('inbox')
            
            # Search for recent emails
            status, messages = mail.search(None, '(SINCE "%s")' % time.strftime('%d-%b-%Y'))
            
            if status == 'OK':
                msg_ids = messages[0].split()
                # Check last 5 emails
                for msg_id in reversed(msg_ids[-5:]):
                    status, msg_data = mail.fetch(msg_id, '(RFC822)')
                    if status == 'OK':
                        raw_email = msg_data[0][1]
                        msg = email_lib.message_from_bytes(raw_email)
                        
                        # Get subject
                        subject = ''
                        for header, value in msg.items():
                            if header.lower() == 'subject':
                                decoded = decode_header(value)
                                subject = ''.join([str(t, c or 'utf-8') if isinstance(t, bytes) else t for t, c in decoded])
                        
                        # Check if it's an AWS OTP email
                        if 'verification' in subject.lower() or 'one-time' in subject.lower() or 'otp' in subject.lower():
                            # Get body
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == 'text/plain':
                                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                        # Extract 6-digit OTP
                                        match = re.search(r'\b(\d{6})\b', body)
                                        if match:
                                            otp_code = match.group(1)
                                            break
                            else:
                                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                                match = re.search(r'\b(\d{6})\b', body)
                                if match:
                                    otp_code = match.group(1)
                        
                        if otp_code:
                            break
                
            mail.logout()
            
            if otp_code:
                break
                
        except Exception as e:
            pass
        
        time.sleep(5)
    
    return otp_code


def main():
    print("=" * 60)
    print("Complete API-Only Account Creation")
    print("=" * 60)
    
    result = create_account()
    
    print(f"\nResult:")
    print(f"  Email: {result.get('email')}")
    print(f"  Name: {result.get('name')}")
    print(f"  Password: {result.get('password')}")
    print(f"  Status: {result.get('status')}")
    if result.get('error'):
        print(f"  Error: {result['error']}")
    if result.get('workflow_id'):
        print(f"  Workflow ID: {result['workflow_id']}")
    if result.get('workflow_state'):
        print(f"  Workflow State: {result['workflow_state']}")
    if result.get('otp'):
        print(f"  OTP: {result['otp']}")
    
    # Save result
    with open('/home/ubuntu/kiro-gen/api_result.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
