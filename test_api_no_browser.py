#!/usr/bin/env python3
"""
API-only account creation.
Uses a minimal browser JUST to get the workflowStateHandle from the redirect chain.
Then switches to pure API calls (with proxy) for everything else.
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
with open('/home/ubuntu/kiro-gen/cloak_fingerprint.txt', 'r') as f:
    CLOAK_FP = f.read().strip()
with open('/home/ubuntu/kiro-gen/profile_fingerprint.txt', 'r') as f:
    PROFILE_FP = f.read().strip()

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Sai", "Arjun", "Reyansh", "Krishna", "Ishaan", "Shaurya", "Atharv",
               "Aadhya", "Saanvi", "Ananya", "Diya", "Kiara", "Ira", "Myra", "Sara", "Aanya", "Anvi",
               "Liam", "Noah", "Ethan", "Mason", "Lucas", "Oliver", "Elijah", "James", "William", "Benjamin"]

LAST_NAMES = ["Sharma", "Verma", "Singh", "Patel", "Kumar", "Gupta", "Mehta", "Joshi", "Reddy", "Nair",
              "Rao", "Pillai", "Menon", "Iyer", "Bhat", "Desai", "Shah", "Chopra", "Malhotra", "Khanna"]


def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"


def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def create_api_session():
    """Create a requests session with SOCKS5 proxy"""
    session = requests.Session()
    proxy_url = f"socks5://api-US:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
    session.proxies = {'http': proxy_url, 'https': proxy_url}
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
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
                
                # Resolve relative URLs
                if location.startswith('/'):
                    from urllib.parse import urlparse
                    parsed = urlparse(current_url)
                    current_url = f"{parsed.scheme}://{parsed.netloc}{location}"
                else:
                    current_url = location
                
                print(f"  [{i}] {status} → {current_url[:100]}")
                
                # Check if we have workflowStateHandle
                if 'workflowStateHandle=' in current_url:
                    wsh = current_url.split('workflowStateHandle=')[1].split('&')[0]
                    return wsh, current_url
                    
            elif status == 200:
                # Check for workflowStateHandle in URL
                if 'workflowStateHandle=' in current_url:
                    wsh = current_url.split('workflowStateHandle=')[1].split('&')[0]
                    return wsh, current_url
                
                # Check for it in HTML
                if 'workflowStateHandle' in resp.text:
                    match = re.search(r'workflowStateHandle["\']?\s*[:=]\s*["\']?([0-9a-f-]{36})', resp.text)
                    if match:
                        return match.group(1), current_url
                
                # If we're on view.awsapps.com/start, the JS redirect goes to portal.sso
                if 'awsapps.com/start' in current_url:
                    # Extract orchestrator_id
                    if 'orchestrator_id=' in current_url:
                        parts = current_url.split('?')[1]
                        orch_id = None
                        cb_url = None
                        for part in parts.split('&'):
                            if part.startswith('orchestrator_id='):
                                orch_id = part.split('=', 1)[1]
                            elif part.startswith('callback_url='):
                                cb_url = part.split('=', 1)[1]
                        
                        if orch_id:
                            from urllib.parse import quote
                            portal_url = f"https://portal.sso.us-east-1.amazonaws.com/login?directory_id=view&orchestrator_id={orch_id}"
                            if cb_url:
                                portal_url += f"&callback_url={cb_url}"
                            print(f"  [{i}] JS redirect → {portal_url[:100]}")
                            current_url = portal_url
                            continue
                
                # If we're on portal.sso, it should redirect to signin.aws
                if 'portal.sso' in current_url and resp.status_code == 200:
                    # Check for meta refresh or JS redirect in the HTML
                    match = re.search(r'window\.location[^=]*=\s*["\']([^"\']+)', resp.text)
                    if match:
                        loc = match.group(1)
                        if loc.startswith('/'):
                            current_url = f"https://portal.sso.us-east-1.amazonaws.com{loc}"
                        else:
                            current_url = loc
                        print(f"  [{i}] JS redirect → {current_url[:100]}")
                        continue
                    
                    # Check for meta refresh
                    match = re.search(r'<meta[^>]*refresh[^>]*content=["\']\d+;\s*url=([^"\']+)', resp.text, re.I)
                    if match:
                        loc = match.group(1)
                        if loc.startswith('/'):
                            current_url = f"https://portal.sso.us-east-1.amazonaws.com{loc}"
                        else:
                            current_url = loc
                        print(f"  [{i}] Meta redirect → {current_url[:100]}")
                        continue
                
                # No redirect found, stop
                print(f"  [{i}] No redirect found at {current_url[:80]}")
                break
            else:
                print(f"  [{i}] Unexpected status: {status}")
                break
                
        except Exception as e:
            print(f"  [{i}] Error: {e}")
            break
    
    return None, current_url


def submit_email_api(session, email, workflow_state_handle):
    """Submit email via API"""
    visitor_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    
    payload = {
        "stepId": "get-identity-user",
        "workflowStateHandle": workflow_state_handle,
        "actionId": "SUBMIT",
        "inputs": [
            {"input_type": "UserRequestInput", "username": email},
            {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FP}
        ],
        "visitorId": visitor_id,
        "requestId": request_id
    }
    
    api_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://us-east-1.signin.aws',
        'Referer': f'https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={workflow_state_handle}',
    }
    
    resp = session.post(
        f'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute',
        json=payload,
        headers=api_headers,
        timeout=30
    )
    
    print(f"    Email submit: HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(f"    Response: {resp.text[:300]}")
    return resp


def submit_signup_api(session, email, workflow_state_handle):
    """Submit signup via API"""
    visitor_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    
    payload = {
        "stepId": "get-identity-user",
        "workflowStateHandle": workflow_state_handle,
        "actionId": "SIGNUP",
        "inputs": [
            {"input_type": "UserRequestInput", "username": email},
            {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FP}
        ],
        "visitorId": visitor_id,
        "requestId": request_id
    }
    
    api_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://us-east-1.signin.aws',
        'Referer': f'https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={workflow_state_handle}',
    }
    
    resp = session.post(
        f'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute',
        json=payload,
        headers=api_headers,
        timeout=30
    )
    
    print(f"    Signup: HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(f"    Response: {resp.text[:300]}")
    return resp


def main():
    print("=" * 60)
    print("API-Only Account Creation (Minimal Browser for WSH)")
    print("=" * 60)
    
    # Generate account details
    email = generate_email()
    name = generate_name()
    print(f"\nEmail: {email}")
    print(f"Name: {name}")
    
    # Register OIDC client (no proxy needed)
    print("\n[1] Registering OIDC client...")
    client_info = register_oidc_client()
    client_id = client_info['clientId']
    print(f"    Client ID: {client_id[:16]}...")
    
    # Create PKCE
    code_verifier, code_challenge = create_pkce()
    
    # Build auth URL
    scopes_encoded = ' '.join(GRANT_SCOPES)
    state = secrets.token_urlsafe(16)
    from urllib.parse import quote
    redirect_uri = 'http://127.0.0.1:9997/oauth/callback'
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
                f'&state={state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    # Create API session with proxy
    print("\n[2] Creating API session with proxy...")
    session = create_api_session()
    
    # Verify proxy
    try:
        ip_resp = session.get('https://ipinfo.io/json', timeout=15)
        ip_data = ip_resp.json()
        print(f"    Proxy IP: {ip_data.get('ip')} ({ip_data.get('city')}, {ip_data.get('country')})")
    except Exception as e:
        print(f"    Proxy check failed: {e}")
    
    # Get workflowStateHandle via redirect chain
    print("\n[3] Following redirect chain to get workflowStateHandle...")
    workflow_state_handle, final_url = get_workflow_state_handle(session, auth_url)
    print(f"    workflowStateHandle: {workflow_state_handle}")
    print(f"    Final URL: {final_url[:100]}")
    
    if not workflow_state_handle:
        print("\nERROR: Could not get workflowStateHandle")
        print("Trying with browser for this step only...")
        
        # Fallback: use browser just to get the WSH
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            page = browser.new_page()
            
            # Navigate to auth URL
            try:
                page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
            except:
                pass
            
            # Wait for sign-in page
            wsh = None
            for i in range(10):
                time.sleep(2)
                try:
                    url = page.url
                    if 'workflowStateHandle=' in url:
                        wsh = url.split('workflowStateHandle=')[1].split('&')[0]
                        print(f"    Got WSH from browser: {wsh}")
                        break
                except:
                    pass
            
            if wsh:
                workflow_state_handle = wsh
            
            browser.close()
    
    if not workflow_state_handle:
        print("ERROR: Could not get workflowStateHandle even with browser")
        return None
    
    # Submit email via API
    print(f"\n[4] Submitting email via API (proxy)...")
    email_resp = submit_email_api(session, email, workflow_state_handle)
    
    # Submit signup via API
    print(f"\n[5] Submitting signup via API (proxy)...")
    signup_resp = submit_signup_api(session, email, workflow_state_handle)
    
    workflow_id = None
    
    if signup_resp.status_code == 200:
        try:
            data = signup_resp.json()
            print(f"    Response keys: {list(data.keys())}")
            
            # The signup response should contain a new workflowStateHandle
            # and possibly a redirect to profile.aws.amazon.com
            wsh2 = data.get('workflowStateHandle', '')
            print(f"    New WSH from signup: {wsh2}")
            
            if wsh2:
                # Make second signup call with stepId="start"
                print(f"    Making second signup call...")
                visitor_id2 = str(uuid.uuid4())
                request_id3 = str(uuid.uuid4())
                
                signup2_payload = {
                    "stepId": "start",
                    "workflowStateHandle": wsh2,
                    "inputs": [
                        {"input_type": "UserRequestInput", "username": email},
                        {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FP} if CLOAK_FP else {"input_type": "UserRequestInput", "username": email}
                    ],
                    "visitorId": visitor_id2,
                    "requestId": request_id3
                }
                
                signup2_resp = session.post(
                    f'https://us-east-1.signin.aws/platform/d-9067642ac7/signup/api/execute',
                    json=signup2_payload,
                    headers={
                        'Content-Type': 'application/json;charset=UTF-8',
                        'Accept': 'application/json, text/plain, */*',
                        'Origin': 'https://us-east-1.signin.aws',
                        'Referer': f'https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={workflow_state_handle}',
                    },
                    timeout=30
                )
                
                print(f"    Signup2: HTTP {signup2_resp.status_code}")
                
                if signup2_resp.status_code == 200:
                    data2 = signup2_resp.json()
                    print(f"    Signup2 keys: {list(data2.keys())}")
                    
                    # Look for workflowID in the response
                    resp_text = json.dumps(data2)
                    import re
                    match = re.search(r'"workflowID"\s*:\s*"([0-9a-f-]{36})"', resp_text)
                    if not match:
                        match = re.search(r'"workflowId"\s*:\s*"([0-9a-f-]{36})"', resp_text)
                    if match:
                        workflow_id = match.group(1)
                        print(f"    FOUND workflowID: {workflow_id}")
                    else:
                        # Check for continueUrl
                        if 'continueUrl' in data2:
                            print(f"    continueUrl: {data2['continueUrl']}")
                            if 'workflowID=' in data2['continueUrl']:
                                workflow_id = data2['continueUrl'].split('workflowID=')[1].split('&')[0]
                                print(f"    workflowID from continueUrl: {workflow_id}")
                        # Check presentationContext
                        if 'presentationContext' in data2:
                            pc_text = json.dumps(data2['presentationContext'])
                            match = re.search(r'"workflowID"\s*:\s*"([0-9a-f-]{36})"', pc_text)
                            if match:
                                workflow_id = match.group(1)
                        # Check workflowResponseData
                        if 'workflowResponseData' in data2:
                            wrd_text = json.dumps(data2['workflowResponseData'])
                            match = re.search(r'"workflowID"\s*:\s*"([0-9a-f-]{36})"', wrd_text)
                            if match:
                                workflow_id = match.group(1)
                    
                    print(f"    Full response: {resp_text[:500]}")
        except Exception as e:
            print(f"    Error parsing: {e}")
    
    if workflow_id:
        print(f"\n[6] Profile workflowID: {workflow_id}")
        
        # Call profile.aws.amazon.com APIs
        profile_headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://profile.aws.amazon.com',
            'Referer': f'https://profile.aws.amazon.com/?workflowID={workflow_id}',
        }
        
        # get-config
        print(f"    Calling /api/get-config...")
        config_resp = session.post('https://profile.aws.amazon.com/api/get-config', json={}, headers=profile_headers, timeout=30)
        print(f"    Config: HTTP {config_resp.status_code}")
        
        # get-app-context
        print(f"    Calling /api/get-app-context...")
        ctx_resp = session.post('https://profile.aws.amazon.com/api/get-app-context', json={"workflowID": workflow_id}, headers=profile_headers, timeout=30)
        print(f"    Context: HTTP {ctx_resp.status_code}")
        
        # start
        print(f"    Calling /api/start...")
        start_payload = {
            "workflowID": workflow_id,
            "browserData": {
                "attributes": {
                    "fingerprint": PROFILE_FP
                },
                "cookies": []
            }
        }
        start_resp = session.post('https://profile.aws.amazon.com/api/start', json=start_payload, headers=profile_headers, timeout=30)
        print(f"    Start: HTTP {start_resp.status_code}")
        
        if start_resp.status_code == 200:
            start_data = start_resp.json()
            print(f"    Start response: {json.dumps(start_data)[:300]}")
            
            workflow_state = start_data.get('workflowState') or start_data.get('state')
            if workflow_state:
                print(f"    workflowState: {workflow_state}")
                
                # send-otp
                print(f"    Calling /api/send-otp...")
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
                otp_resp = session.post('https://profile.aws.amazon.com/api/send-otp', json=otp_payload, headers=profile_headers, timeout=30)
                print(f"    Send OTP: HTTP {otp_resp.status_code}")
                print(f"    OTP Response: {otp_resp.text[:300]}")
    else:
        print(f"    Could not find workflowID in signup response")
        print(f"    Full signup response: {signup_resp.text[:500]}")
    
    print(f"\n{'='*60}")
    print("Done!")
    print(f"{'='*60}")
    
    return workflow_state_handle


if __name__ == "__main__":
    main()
