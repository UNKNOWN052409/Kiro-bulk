"""Debug the page rendering issue."""
from playwright.sync_api import sync_playwright
import time, secrets, hashlib, base64

def safe_eval(page, js):
    try:
        return page.evaluate(js)
    except Exception:
        return ''

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Check current URL
    print(f"Initial URL: {page.url}")
    
    # Navigate to OIDC authorize
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(secrets.token_urlsafe(64).encode()).digest()).rstrip(b'=').decode()
    auth_url = f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id=test-debug&redirect_uri=http://127.0.0.1:9999/callback&scopes=codewhisperer:completions&state=test&code_challenge={code_challenge}&code_challenge_method=S256'
    
    print(f"Navigating to OIDC authorize...")
    try:
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        print(f"  Navigation succeeded, URL: {page.url}")
    except Exception as e:
        print(f"  Navigation error: {e}")
        print(f"  URL after error: {page.url}")
    
    # Wait and check
    for i in range(10):
        time.sleep(3)
        url = page.url
        body = safe_eval(page, "document.body ? document.body.innerText : ''")
        html_len = safe_eval(page, "document.documentElement ? document.documentElement.innerHTML.length : 0")
        title = safe_eval(page, "document.title")
        print(f"  [{i*3}s] URL: {url[:80]} | Title: {title[:30]} | Body: {body[:60] if body else 'empty'} | HTML len: {html_len}")
    
    page.close()
    context.close()
