"""Test OIDC authorize with a valid client."""
from playwright.sync_api import sync_playwright
import time, uuid, requests, secrets, hashlib, base64

def safe_eval(page, js):
    try:
        return page.evaluate(js)
    except Exception:
        return ''

# Register a valid client
reg_payload = {
    "clientName": f"kiro-test-{uuid.uuid4().hex[:6]}",
    "clientType": "public",
    "scopes": ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"],
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9998/oauth/callback"],
    "issuerUrl": "https://view.awsapps.com/start"
}
reg_resp = requests.post('https://oidc.us-east-1.amazonaws.com/client/register', json=reg_payload, timeout=10)
print(f"Register status: {reg_resp.status_code}")
if reg_resp.status_code != 200:
    print(f"  Error: {reg_resp.text}")
    exit(1)

reg_data = reg_resp.json()
client_id = reg_data['clientId']
print(f"Client ID: {client_id}")

code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()

auth_url = f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id={client_id}&redirect_uri=http://127.0.0.1:9998/oauth/callback&scopes=codewhisperer:completions codewhisperer:analysis codewhisperer:conversations codewhisperer:transformations codewhisperer:taskassist&state=test&code_challenge={code_challenge}&code_challenge_method=S256'

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    print(f"\nNavigating to OIDC authorize with valid client...")
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    
    for i in range(15):
        time.sleep(3)
        url = page.url
        body = safe_eval(page, "document.body ? document.body.innerText : ''")
        title = safe_eval(page, "document.title")
        buttons = safe_eval(page, "Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        print(f"  [{i*3}s] URL: {url[:70]} | Title: {title[:20]} | Body: {body[:60] if body else 'empty'}")
        print(f"           Buttons: {buttons[:60]}")
        if body and len(body) > 20:
            break
    
    page.close()
    context.close()
