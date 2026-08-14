#!/usr/bin/env python3
"""
Complete flow: navigate through sign-in, wait for SPA to load,
fill name, submit, then continue to OTP.
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
from urllib.parse import quote

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

# Random human names
FIRST_NAMES = ["Aditya", "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Karan", "Deepika", "Arjun", 
               "Meera", "Rohan", "Kavya", "Nikhil", "Divya", "Siddharth", "Pooja", "Vishal", "Ritu", "Aman",
               "James", "Sarah", "Michael", "Emma", "David", "Olivia", "Daniel", "Sophia", "Matthew", "Isabella",
               "Christopher", "Mia", "Andrew", "Charlotte", "Joshua", "Amelia", "Ryan", "Harper", "Brandon", "Evelyn"]
LAST_NAMES = ["Sharma", "Patel", "Singh", "Kumar", "Gupta", "Verma", "Mehta", "Agarwal", "Joshi", "Reddy",
              "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Anderson", "Taylor", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Moore", "Clark"]

def generate_account():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    email = f"{prefix}@havenhaus.in"
    return first, last, email

first_name, last_name, email_addr = generate_account()
full_name = f"{first_name} {last_name}"
print(f"Account: {full_name} <{email_addr}>")

# Register OIDC client
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9997/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

# PKCE
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = 'http://127.0.0.1:9997/oauth/callback'
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

print(f"\n[Step 1] Navigating through sign-in flow...")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    )
    page = browser.new_page()
    
    try:
        # Navigate to auth URL
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)
        
        # Fill email
        email_input = page.locator('input[type="email"]').first
        email_input.fill(email_addr)
        time.sleep(1)
        
        # Click Continue
        page.locator('button:has-text("Continue")').first.click()
        time.sleep(5)
        
        # Click Sign up
        for selector in ['button:has-text("Sign up")', 'button:has-text("Create account")', 'button:has-text("Get started")']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click()
                    print(f"  Clicked: {selector}")
                    break
            except:
                pass
        
        time.sleep(3)
        
        # Wait for profile.aws.amazon.com with workflowID
        workflow_id = None
        for i in range(10):
            time.sleep(1)
            url = page.url
            if 'profile.aws.amazon.com' in url and 'workflowID=' in url:
                raw = url.split('workflowID=')[1]
                workflow_id = raw.split('#')[0].split('&')[0]
                if re.match(r'[0-9a-f-]{36}$', workflow_id):
                    print(f"  workflowID: {workflow_id}")
                    break
        
        if not workflow_id:
            print("  ERROR: No workflowID found")
            browser.close()
            raise Exception("No workflowID found")
        
        # [Step 2] Wait for SPA to load
        print(f"\n[Step 2] Waiting for SPA to load...")
        for i in range(30):
            time.sleep(2)
            try:
                body_text = page.inner_text('body')
                if len(body_text) > 100:
                    print(f"  SPA loaded after {i*2}s!")
                    print(f"  Body: {body_text[:150]}")
                    break
            except:
                pass
        
        # [Step 3] Fill name
        print(f"\n[Step 3] Filling name: {full_name}")
        try:
            # Find the name input (has placeholder like "Maria José Silva")
            name_input = page.locator('input[type="text"][placeholder]').first
            name_input.click()
            time.sleep(0.5)
            # Type character by character for human-like behavior
            for char in full_name:
                name_input.type(char, delay=random.uniform(50, 150))
                time.sleep(random.uniform(0.01, 0.05))
            time.sleep(1)
            print(f"  Name filled: {full_name}")
        except Exception as e:
            print(f"  Error filling name: {e}")
            # Try alternative selectors
            for selector in ['input[placeholder*="Name"]', 'input[name="name"]', 'input[type="text"]']:
                try:
                    inp = page.locator(selector).first
                    if inp.is_visible():
                        inp.click()
                        time.sleep(0.5)
                        inp.type(full_name, delay=random.uniform(50, 150))
                        print(f"  Name filled using: {selector}")
                        break
                except:
                    pass
        
        time.sleep(2)
        
        # [Step 4] Click Continue
        print(f"\n[Step 4] Clicking Continue...")
        try:
            page.locator('button:has-text("Continue")').first.click()
            print("  Continue clicked")
        except Exception as e:
            print(f"  Error clicking Continue: {e}")
        
        # Wait for next page (OTP)
        time.sleep(5)
        print(f"  URL after Continue: {page.url[:120]}")
        
        # Check what's on the page
        try:
            body_text = page.inner_text('body')
            print(f"  Body: {body_text[:300]}")
        except:
            pass
        
        browser.close()
    except Exception as e:
        print(f"  Error: {e}")
        browser.close()

print(f"\n{'='*60}")
