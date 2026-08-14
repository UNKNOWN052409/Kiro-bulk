#!/usr/bin/env python3
"""
Direct API client for AWS OIDC account creation.
No browser needed - just HTTP requests through residential proxy.

This replicates the exact API flow captured via MITM.
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
import sys
import os

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

# ProxyRise API key
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'

# Load the CloakBrowser fingerprint
with open('/home/ubuntu/kiro-gen/cloak_fingerprint.txt', 'r') as f:
    CLOAK_FINGERPRINT = f.read().strip()

with open('/home/ubuntu/kiro-gen/profile_fingerprint.txt', 'r') as f:
    PROFILE_FINGERPRINT = f.read().strip()

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Sai", "Arjun", "Reyansh", "Krishna", "Ishaan", "Shaurya", "Atharv",
               "Aadhya", "Saanvi", "Ananya", "Diya", "Kiara", "Ira", "Myra", "Sara", "Aanya", "Anvi",
               "Liam", "Noah", "Ethan", "Mason", "Lucas", "Oliver", "Elijah", "James", "William", "Benjamin",
               "Emma", "Olivia", "Ava", "Isabella", "Sophia", "Mia", "Charlotte", "Amelia", "Harper", "Evelyn"]

LAST_NAMES = ["Sharma", "Verma", "Singh", "Patel", "Kumar", "Gupta", "Mehta", "Joshi", "Reddy", "Nair",
              "Rao", "Pillai", "Menon", "Iyer", "Bhat", "Desai", "Shah", "Chopra", "Malhotra", "Khanna",
              "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]


def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"


def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


class ProxySession:
    """HTTP session that routes through ProxyRise residential proxy"""
    
    def __init__(self, country='US'):
        self.proxy_url = f"socks5://api-{country}:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
        self.session = requests.Session()
        self.session.proxies = {
            'http': self.proxy_url,
            'https': self.proxy_url
        }
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://profile.aws.amazon.com',
            'Referer': 'https://profile.aws.amazon.com/',
        })
    
    def post(self, url, json_data=None, **kwargs):
        kwargs.pop('json', None)
        return self.session.post(url, json=json_data, timeout=30, **kwargs)
    
    def get(self, url, **kwargs):
        return self.session.get(url, timeout=30, **kwargs)


def step1_register_oidc_client():
    """Register a new OIDC client with AWS (no proxy needed)"""
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


def step2_generate_pkce():
    """Generate PKCE code verifier and challenge"""
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    return code_verifier, code_challenge


def step3_navigate_and_get_workflow():
    """Navigate through the OIDC flow to get the workflow state"""
    # This requires a browser to get the initial redirect chain
    # We'll use CloakBrowser for this step only, then switch to API calls
    from cloakbrowser import launch
    
    code_verifier, code_challenge = step2_generate_pkce()
    client_info = step1_register_oidc_client()
    client_id = client_info['clientId']
    
    scopes_encoded = ' '.join(GRANT_SCOPES)
    state = secrets.token_urlsafe(16)
    redirect_uri = 'http://127.0.0.1:9999/oauth/callback'
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={redirect_uri}&scopes={scopes_encoded}'
                f'&state={state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    email = generate_email()
    name = generate_name()
    
    print(f"  Email: {email}")
    print(f"  Name: {name}")
    print(f"  Client: {client_id[:16]}...")
    
    # Launch browser for initial navigation
    browser = launch(headless=False, humanize=True)
    page = browser.new_page()
    
    # Navigate to auth URL
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    
    # Wait for sign-in page
    workflow_state_handle = None
    visitor_id = None
    
    for i in range(15):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            url = page.url
            if 'email' in body.lower() and 'continue' in body.lower():
                # Extract workflowStateHandle from URL
                if 'workflowStateHandle=' in url:
                    workflow_state_handle = url.split('workflowStateHandle=')[1].split('&')[0]
                print(f"  Sign-in page loaded: {url[:80]}")
                break
        except:
            pass
    
    if not workflow_state_handle:
        # Try to extract from current URL
        url = page.url
        if 'workflowStateHandle=' in url:
            workflow_state_handle = url.split('workflowStateHandle=')[1].split('&')[0]
    
    print(f"  workflowStateHandle: {workflow_state_handle}")
    
    # Close browser - we'll continue with API calls
    browser.close()
    
    return {
        'email': email,
        'name': name,
        'workflow_state_handle': workflow_state_handle,
        'code_verifier': code_verifier,
        'client_id': client_id,
    }


def step4_submit_email_api(session, email, workflow_state_handle):
    """Submit email via API"""
    visitor_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    
    payload = {
        "stepId": "get-identity-user",
        "workflowStateHandle": workflow_state_handle,
        "actionId": "SUBMIT",
        "inputs": [
            {"input_type": "UserRequestInput", "username": email},
            {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FINGERPRINT}
        ],
        "visitorId": visitor_id,
        "requestId": request_id
    }
    
    resp = session.post(
        f'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute',
        json=payload
    )
    
    print(f"  Email submit: HTTP {resp.status_code}")
    print(f"  Response: {resp.text[:300]}")
    
    return resp


def step5_signup_api(session, email, workflow_state_handle):
    """Submit signup via API"""
    visitor_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    
    payload = {
        "stepId": "get-identity-user",
        "workflowStateHandle": workflow_state_handle,
        "actionId": "SIGNUP",
        "inputs": [
            {"input_type": "UserRequestInput", "username": email},
            {"input_type": "FingerPrintRequestInput", "fingerPrint": CLOAK_FINGERPRINT}
        ],
        "visitorId": visitor_id,
        "requestId": request_id
    }
    
    resp = session.post(
        f'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute',
        json=payload
    )
    
    print(f"  Signup: HTTP {resp.status_code}")
    print(f"  Response: {resp.text[:300]}")
    
    return resp


def step6_profile_start_api(session, workflow_id):
    """Start profile workflow via API"""
    payload = {
        "workflowID": workflow_id,
        "browserData": {
            "attributes": {
                "fingerprint": PROFILE_FINGERPRINT
            },
            "cookies": []
        }
    }
    
    resp = session.post(
        'https://profile.aws.amazon.com/api/start',
        json=payload
    )
    
    print(f"  Profile start: HTTP {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")
    
    return resp


def step7_send_otp_api(session, workflow_state, email):
    """Send OTP via API"""
    payload = {
        "workflowState": workflow_state,
        "email": email,
        "browserData": {
            "attributes": {
                "fingerprint": PROFILE_FINGERPRINT
            },
            "cookies": []
        }
    }
    
    resp = session.post(
        'https://profile.aws.amazon.com/api/send-otp',
        json=payload
    )
    
    print(f"  Send OTP: HTTP {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")
    
    return resp


def main():
    """Run the full account creation via API"""
    print("=" * 60)
    print("Kiro AI Account Creation - Direct API (No Browser)")
    print("=" * 60)
    
    # Step 1-3: Initial setup with browser (just for navigation)
    print("\n[1/7] Initial setup (browser for redirect chain)...")
    initial = step3_navigate_and_get_workflow()
    
    if not initial['workflow_state_handle']:
        print("ERROR: Could not get workflow state handle")
        return None
    
    # Step 4: Create proxy session
    print("\n[2/7] Creating proxy session (US residential)...")
    session = ProxySession(country='US')
    
    # Verify proxy works
    try:
        ip_resp = session.get('https://ipinfo.io/json')
        ip_data = ip_resp.json()
        print(f"  Proxy IP: {ip_data.get('ip')} ({ip_data.get('city')}, {ip_data.get('country')})")
    except Exception as e:
        print(f"  Proxy check failed: {e}")
        # Fall back to direct
        session = ProxySession.__new__(ProxySession)
        session.session = requests.Session()
        session.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://profile.aws.amazon.com',
            'Referer': 'https://profile.aws.amazon.com/',
        })
    
    # Step 5: Submit email via API
    print(f"\n[3/7] Submitting email via API: {initial['email']}")
    email_resp = step4_submit_email_api(session, initial['email'], initial['workflow_state_handle'])
    
    # Step 6: Signup via API
    print(f"\n[4/7] Submitting signup via API...")
    signup_resp = step5_signup_api(session, initial['email'], initial['workflow_state_handle'])
    
    # Step 7: Navigate to profile page (need browser for this)
    print(f"\n[5/7] Getting profile workflow ID...")
    
    # We need the browser to get the profile.aws.amazon.com workflow ID
    # Let's use the browser just for this redirect
    from cloakbrowser import launch
    browser = launch(headless=False, humanize=True)
    page = browser.new_page()
    
    # Navigate to the signup URL (should redirect to profile.aws.amazon.com)
    auth_url = f"https://us-east-1.signin.aws/platform/d-9067642ac7/signup?workflowStateHandle={initial['workflow_state_handle']}"
    try:
        page.goto(auth_url, wait_until='domcontentloaded', timeout=15000)
    except:
        pass
    
    # Wait for redirect to profile.aws.amazon.com
    workflow_id = None
    for i in range(20):
        time.sleep(2)
        try:
            url = page.url
            if 'profile.aws.amazon.com' in url:
                if 'workflowID=' in url:
                    workflow_id = url.split('workflowID=')[1].split('&')[0].split('#')[0]
                print(f"  Profile page: {url[:80]}")
                break
        except:
            pass
    
    print(f"  workflowID: {workflow_id}")
    browser.close()
    
    if not workflow_id:
        print("ERROR: Could not get profile workflow ID")
        return None
    
    # Step 8: Profile start API
    print(f"\n[6/7] Starting profile workflow via API...")
    profile_resp = step6_profile_start_api(session, workflow_id)
    
    # Parse response to get workflowState
    workflow_state = None
    try:
        resp_data = profile_resp.json()
        workflow_state = resp_data.get('workflowState') or resp_data.get('state')
        print(f"  workflowState: {workflow_state}")
    except:
        print(f"  Could not parse profile response: {profile_resp.text[:200]}")
    
    if not workflow_state:
        print("ERROR: Could not get workflow state from profile response")
        return None
    
    # Step 9: Send OTP
    print(f"\n[7/7] Sending OTP via API...")
    otp_resp = step7_send_otp_api(session, workflow_state, initial['email'])
    
    print(f"\n{'='*60}")
    print("Account creation initiated!")
    print(f"  Email: {initial['email']}")
    print(f"  Name: {initial['name']}")
    print(f"  Workflow ID: {workflow_id}")
    print(f"  Workflow State: {workflow_state}")
    print(f"  Next: Enter OTP from Gmail")
    print(f"{'='*60}")
    
    return initial


if __name__ == "__main__":
    main()
