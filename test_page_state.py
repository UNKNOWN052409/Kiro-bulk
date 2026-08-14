"""Check the page state after logout."""
from playwright.sync_api import sync_playwright
import time

def safe_eval(page, js):
    try:
        return page.evaluate(js)
    except Exception:
        return ''

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=10000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Check current state (should be logged out after previous run)
    print(f"URL: {page.url}")
    
    # Try navigating to OIDC authorize URL
    import uuid, secrets, hashlib, base64
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    
    client_id = "test-client"
    redirect_uri = "http://127.0.0.1:8999/oauth/callback"
    scopes = "codewhisperer:completions codewhisperer:analysis codewhisperer:conversations codewhisperer:transformations codewhisperer:taskassist"
    
    auth_url = f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scopes={scopes}&state=test&code_challenge={code_challenge}&code_challenge_method=S256'
    
    print(f"\nNavigating to: {auth_url[:100]}...")
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    
    for i in range(10):
        time.sleep(3)
        url = page.url
        body = safe_eval(page, "document.body ? document.body.innerText : ''")
        buttons = safe_eval(page, "Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        print(f"  [{i*3}s] URL: {url[:60]} | Body: {body[:50] if body else 'empty'} | Buttons: {buttons[:50]}")
        if 'Allow' in buttons or 'email' in body.lower():
            break
    
    page.close()
    context.close()
