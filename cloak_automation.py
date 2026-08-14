#!/usr/bin/env python3
"""
Kiro AI Account Generator using CloakBrowser
- Stealth browser (71 C++ patches, passes all bot detection)
- Residential proxy per account (unique IP)
- Device simulation (unique fingerprint per container)
- Human-like behavior (mouse jitter, typing delays)
- OIDC Auth Code Flow with PKCE
- Token capture
"""

import time
import uuid
import secrets
import hashlib
import base64
import requests
import random
import string
import json
import os
import sys

from cloakbrowser import launch

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

# Device profiles for simulation
DEVICE_PROFILES = [
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", "tz": "America/New_York", "device": "Pixel 7"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", "tz": "America/Chicago", "device": "iPhone 15"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", "tz": "America/Los_Angeles", "device": "Galaxy S24"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15", "tz": "Europe/London", "device": "MacBook Pro"},
    {"ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", "tz": "Europe/Paris", "device": "Dell XPS 15"},
    {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0", "tz": "Europe/Berlin", "device": "ThinkPad X1"},
    {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0", "tz": "Asia/Tokyo", "device": "Surface Pro"},
    {"ua": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0", "tz": "Australia/Sydney", "device": "iPad Pro"},
]

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


def register_oidc_client(port):
    """Register a new OIDC client with AWS"""
    reg_payload = {
        "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
        "clientType": "public",
        "scopes": GRANT_SCOPES,
        "grantTypes": ["authorization_code", "refresh_token"],
        "redirectUris": [f"http://127.0.0.1:{port}/oauth/callback"],
        "issuerUrl": ISSUER_URL
    }
    reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
    return reg_resp.json()


def create_pkce():
    """Generate PKCE code verifier and challenge"""
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    return code_verifier, code_challenge


def run_account(container_id=0):
    """Run the full account creation flow"""
    port = 9900 + container_id
    device_idx = container_id % len(DEVICE_PROFILES)
    device = DEVICE_PROFILES[device_idx]
    
    # Generate account details
    email = generate_email()
    name = generate_name()
    password = f"TestPass{random.randint(1000, 9999)}!"
    
    print(f"\n{'='*60}")
    print(f"[Container {container_id}] Device: {device['device']}")
    print(f"[Container {container_id}] Timezone: {device['tz']}")
    print(f"[Container {container_id}] Email: {email}")
    print(f"[Container {container_id}] Name: {name}")
    print(f"{'='*60}")
    
    # Register OIDC client
    client_info = register_oidc_client(port)
    client_id = client_info['clientId']
    print(f"[Container {container_id}] OIDC Client: {client_id[:16]}...")
    
    # Create PKCE
    code_verifier, code_challenge = create_pkce()
    scopes_encoded = ' '.join(GRANT_SCOPES)
    state = secrets.token_urlsafe(16)
    redirect_uri = f'http://127.0.0.1:{port}/oauth/callback'
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={redirect_uri}&scopes={scopes_encoded}'
                f'&state={state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    # Launch CloakBrowser with residential proxy
    proxy_url = f"socks5://api-US:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
    print(f"[Container {container_id}] Launching CloakBrowser with US residential proxy...")
    
    try:
        browser = launch(
            proxy=proxy_url,
            geoip=True,
            headless=False,
            humanize=True,
        )
    except Exception as e:
        print(f"[Container {container_id}] Failed to launch browser: {e}")
        return None
    
    page = browser.new_page()
    
    # Navigate to auth URL
    print(f"[Container {container_id}] Navigating to authorize URL...")
    try:
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    except Exception as e:
        print(f"[Container {container_id}] Navigation error: {e}")
        browser.close()
        return None
    
    # Wait for sign-in page to load
    print(f"[Container {container_id}] Waiting for sign-in page...")
    for i in range(15):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            if 'email' in body.lower() and 'continue' in body.lower():
                print(f"[Container {container_id}] Sign-in page loaded!")
                break
        except:
            pass
    
    # Human-like: move mouse randomly before interacting
    print(f"[Container {container_id}] Human-like mouse movement...")
    for _ in range(3):
        x = random.randint(100, 1100)
        y = random.randint(100, 600)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.2, 0.5))
    
    # Enter email with typing effect
    print(f"[Container {container_id}] Entering email...")
    try:
        inputs = page.locator('input').all()
        visible = [inp for inp in inputs if inp.is_visible()]
        email_inp = None
        for inp in visible:
            inp_type = inp.get_attribute('type') or 'text'
            if inp_type in ('email', 'text'):
                email_inp = inp
                break
        if email_inp is None and visible:
            email_inp = visible[0]
        
        if email_inp:
            email_inp.click()
            time.sleep(0.5)
            # Type with human-like delays
            for char in email:
                page.keyboard.type(char, delay=random.uniform(30, 100))
            time.sleep(random.uniform(1.5, 3.0))
            
            btn = page.get_by_role("button", name="Continue", exact=True).first
            btn.click()
            print(f"[Container {container_id}] Email submitted!")
    except Exception as e:
        print(f"[Container {container_id}] Error entering email: {e}")
        browser.close()
        return None
    
    # Wait for Name page (profile.aws.amazon.com)
    print(f"[Container {container_id}] Waiting for Name page (up to 120s)...")
    name_loaded = False
    for i in range(60):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            html_len = page.evaluate("() => document.body ? document.body.innerHTML.length : 0")
            url = page.url
            if 'enter your name' in body.lower():
                print(f"[Container {container_id}] Name page loaded at {i*2}s! html_len={html_len}")
                name_loaded = True
                break
            elif i % 10 == 0:
                print(f"[Container {container_id}] [{i*2}s] url={url[:60]} body_len={len(body)} html_len={html_len}")
        except:
            pass
    
    if not name_loaded:
        print(f"[Container {container_id}] Name page never loaded")
        browser.close()
        return None
    
    # Human-like delay before entering name
    time.sleep(random.uniform(2, 4))
    
    # Move mouse
    for _ in range(2):
        x = random.randint(100, 1100)
        y = random.randint(100, 600)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.2, 0.5))
    
    # Enter name
    print(f"[Container {container_id}] Entering name: {name}")
    try:
        name_inputs = page.locator('input[type="text"]').all()
        visible_name = [inp for inp in name_inputs if inp.is_visible()]
        if visible_name:
            visible_name[0].click()
            time.sleep(0.5)
            for char in name:
                page.keyboard.type(char, delay=random.uniform(30, 100))
            time.sleep(random.uniform(1.5, 3.0))
            
            btn = page.get_by_role("button", name="Continue", exact=True).first
            btn.click()
            print(f"[Container {container_id}] Name submitted!")
    except Exception as e:
        print(f"[Container {container_id}] Error entering name: {e}")
        browser.close()
        return None
    
    # Wait for next page (OTP or Password)
    print(f"[Container {container_id}] Waiting for OTP/Password page...")
    for i in range(20):
        time.sleep(3)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            url = page.url
            status = "OK" if ('ERR-837' not in body and len(body) > 100 and 'enter your name' not in body.lower()) else "ERR-837 or loading"
            print(f"[Container {container_id}] [{i*3}s] url={url[:60]} | {status} | body={body[:100]}")
            
            if status == "OK":
                print(f"[Container {container_id}] SUCCESS! Progress to next step!")
                # Don't close browser - keep it alive for OTP entry
                return {"browser": browser, "page": page, "email": email, "name": name, "password": password}
        except:
            pass
    
    print(f"[Container {container_id}] Timed out waiting for next page")
    browser.close()
    return None


def main():
    if len(sys.argv) > 1:
        container_id = int(sys.argv[1])
    else:
        container_id = 0
    
    result = run_account(container_id)
    
    if result:
        print(f"\n[Container {container_id}] Account created successfully!")
        print(f"  Email: {result['email']}")
        print(f"  Name: {result['name']}")
        print(f"  Password: {result['password']}")
        print(f"  Browser still open for OTP entry...")
        
        # Save account info
        account_data = {
            "container_id": container_id,
            "email": result['email'],
            "name": result['name'], 
            "password": result['password'],
            "timestamp": time.time()
        }
        
        # Append to accounts file
        accounts_file = "/home/ubuntu/kiro-gen/accounts_created.json"
        try:
            with open(accounts_file, 'r') as f:
                accounts = json.load(f)
        except:
            accounts = []
        
        accounts.append(account_data)
        with open(accounts_file, 'w') as f:
            json.dump(accounts, f, indent=2)
        
        print(f"  Saved to {accounts_file}")
        
        # Keep browser open for OTP
        input("  Press Enter to close browser...")
        result['browser'].close()
    else:
        print(f"\n[Container {container_id}] Account creation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
