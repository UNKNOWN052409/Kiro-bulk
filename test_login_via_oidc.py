"""Test if login page renders via OIDC redirect."""
from playwright.sync_api import sync_playwright
import time, uuid, requests, secrets, hashlib, base64

# Register valid client
reg_payload = {
    "clientName": f"kiro-test-{uuid.uuid4().hex[:6]}",
    "clientType": "public",
    "scopes": ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"],
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9997/oauth/callback"],
    "issuerUrl": "https://view.awsapps.com/start"
}
reg_resp = requests.post('https://oidc.us-east-1.amazonaws.com/client/register', json=reg_payload, timeout=10)
if reg_resp.status_code != 200:
    print(f"Register failed: {reg_resp.text}")
    exit(1)

client_id = reg_resp.json()['clientId']
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes = 'codewhisperer:completions codewhisperer:analysis codewhisperer:conversations codewhisperer:transformations codewhisperer:taskassist'
auth_url = f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id={client_id}&redirect_uri=http://127.0.0.1:9997/oauth/callback&scopes={scopes}&state=test&code_challenge={code_challenge}&code_challenge_method=S256'

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    print("Navigating to OIDC authorize...")
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(15)
    
    # Get page info
    print(f"URL: {page.url[:100]}")
    
    # Try to get content
    try:
        html = page.content()
        print(f"HTML length: {len(html)}")
    except Exception as e:
        print(f"content() error: {e}")
    
    # Try Playwright locators
    try:
        inputs = page.locator('input').all()
        print(f"Inputs found: {len(inputs)}")
    except Exception as e:
        print(f"input locator error: {e}")
    
    try:
        btns = page.locator('button').all()
        print(f"Buttons found: {len(btns)}")
    except Exception as e:
        print(f"button locator error: {e}")
    
    # Try email locator
    try:
        email_inp = page.locator('input[type="email"]').all()
        print(f"Email inputs: {len(email_inp)}")
    except Exception as e:
        print(f"email input error: {e}")
    
    # Try text-based
    try:
        el = page.get_by_text("Email").first
        visible = el.is_visible(timeout=2000)
        print(f"'Email' text visible: {visible}")
    except Exception as e:
        print(f"text lookup error: {e}")
    
    page.close()
    context.close()
