#!/usr/bin/env python3
"""
Full API-based account creation - no browser needed at all.
Follows the redirect chain programmatically.
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

def register_oidc_client():
    reg_payload = {
        "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
        "clientType": "public",
        "scopes": GRANT_SCOPES,
        "grantTypes": ["authorization_code", "refresh_token"],
        "redirectUris": ["http://127.0.0.1:9999/oauth/callback"],
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

def create_session(proxy=True, country='US'):
    """Create a requests session with or without proxy"""
    session = requests.Session()
    if proxy:
        proxy_url = f"socks5://api-{country}:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
        session.proxies = {'http': proxy_url, 'https': proxy_url}
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    return session

def follow_redirects(session, url, max_redirects=10):
    """Follow redirects manually to capture intermediate URLs"""
    current_url = url
    urls_visited = []
    
    for _ in range(max_redirects):
        urls_visited.append(current_url)
        try:
            resp = session.get(current_url, allow_redirects=False, timeout=15)
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get('Location', '')
                if location:
                    if location.startswith('/'):
                        from urllib.parse import urlparse
                        parsed = urlparse(current_url)
                        current_url = f"{parsed.scheme}://{parsed.netloc}{location}"
                    else:
                        current_url = location
                else:
                    break
            else:
                break
        except Exception as e:
            print(f"  Redirect error: {e}")
            break
    
    return urls_visited, current_url


def main():
    print("=" * 60)
    print("Full API Account Creation (No Browser)")
    print("=" * 60)
    
    # Step 1: Register OIDC client
    print("\n[1] Registering OIDC client...")
    client_info = register_oidc_client()
    client_id = client_info['clientId']
    print(f"    Client ID: {client_id}")
    
    # Step 2: Create PKCE
    code_verifier, code_challenge = create_pkce()
    
    # Step 3: Build auth URL
    scopes_encoded = ' '.join(GRANT_SCOPES)
    state = secrets.token_urlsafe(16)
    redirect_uri = 'http://127.0.0.1:9999/oauth/callback'
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={redirect_uri}&scopes={scopes_encoded}'
                f'&state={state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    print(f"\n[2] Auth URL: {auth_url[:100]}...")
    
    # Step 4: Follow redirect chain to get workflowStateHandle
    print("\n[3] Following redirect chain...")
    session = create_session(proxy=True)  # Use proxy for all requests
    
    # Verify proxy
    try:
        ip_resp = session.get('https://ipinfo.io/json', timeout=15)
        ip_data = ip_resp.json()
        print(f"    Proxy IP: {ip_data.get('ip')} ({ip_data.get('city')}, {ip_data.get('country')})")
    except Exception as e:
        print(f"    Proxy check failed: {e}")
    
    # Follow redirects from auth URL
    urls_visited, final_url = follow_redirects(session, auth_url)
    print(f"    Visited {len(urls_visited)} URLs")
    for u in urls_visited:
        print(f"      → {u[:100]}")
    print(f"    Final: {final_url[:120]}")
    
    # Extract workflowStateHandle from final URL
    workflow_state_handle = None
    if 'workflowStateHandle=' in final_url:
        workflow_state_handle = final_url.split('workflowStateHandle=')[1].split('&')[0]
    elif 'workflowStateHandle=' in str(urls_visited):
        for u in urls_visited:
            if 'workflowStateHandle=' in u:
                workflow_state_handle = u.split('workflowStateHandle=')[1].split('&')[0]
                break
    
    print(f"\n    workflowStateHandle: {workflow_state_handle}")
    
    if not workflow_state_handle:
        print("    ERROR: Could not extract workflowStateHandle")
        # Try to get it from the last URL
        print(f"    Last URL: {final_url}")
        return
    
    # Step 5: Get account details
    email = generate_email()
    name = generate_name()
    print(f"\n[4] Account: {email} / {name}")
    
    # Step 6: Submit email via API with proxy
    print(f"\n[5] Submitting email via API (through proxy)...")
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
    
    # Set proper headers for the API call
    api_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://us-east-1.signin.aws',
        'Referer': 'https://us-east-1.signin.aws/platform/d-9067642ac7/login',
    }
    
    resp = session.post(
        f'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute',
        json=payload,
        headers=api_headers,
        timeout=30
    )
    
    print(f"    HTTP {resp.status_code}")
    print(f"    Response: {resp.text[:500]}")
    
    if resp.status_code == 200:
        try:
            data = resp.json()
            print(f"    Next step: {data.get('stepId')}")
            print(f"    Actions: {data.get('actions')}")
        except:
            pass
    
    # Step 7: Signup via API
    print(f"\n[6] Submitting signup via API...")
    request_id2 = str(uuid.uuid4())
    
    payload2 = {
        "stepId": "get-identity-user",
        "workflowStateHandle": workflow_state_handle,
        "actionId": "SIGNUP",
        "inputs": [
            {"input_type": "UserRequestInput", "username": email},
            {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FP}
        ],
        "visitorId": visitor_id,
        "requestId": request_id2
    }
    
    resp2 = session.post(
        f'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute',
        json=payload2,
        headers=api_headers,
        timeout=30
    )
    
    print(f"    HTTP {resp2.status_code}")
    print(f"    Response: {resp2.text[:500]}")
    
    if resp2.status_code == 200:
        try:
            data2 = resp2.json()
            print(f"    Next step: {data2.get('stepId')}")
            print(f"    Actions: {data2.get('actions')}")
            # Check for redirect URL
            if 'continueUrl' in data2:
                print(f"    Redirect: {data2['continueUrl']}")
        except:
            pass
    
    print(f"\n{'='*60}")
    print("Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
