"""Wait longer for the login page to fully load."""
from playwright.sync_api import sync_playwright
import time, uuid, requests, secrets, hashlib, base64

reg_payload = {
    "clientName": f"kiro-test-{uuid.uuid4().hex[:6]}",
    "clientType": "public",
    "scopes": ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"],
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9996/oauth/callback"],
    "issuerUrl": "https://view.awsapps.com/start"
}
reg_resp = requests.post('https://oidc.us-east-1.amazonaws.com/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes = 'codewhisperer:completions codewhisperer:analysis codewhisperer:conversations codewhisperer:transformations codewhisperer:taskassist'
auth_url = f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id={client_id}&redirect_uri=http://127.0.0.1:9996/oauth/callback&scopes={scopes}&state=test&code_challenge={code_challenge}&code_challenge_method=S256'

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    
    # Wait much longer
    for i in range(20):
        time.sleep(3)
        url = page.url
        try:
            html = page.content()
            html_len = len(html)
        except:
            html_len = -1
        
        try:
            inputs = page.locator('input').count()
        except:
            inputs = -1
        
        try:
            btns = page.locator('button').count()
        except:
            btns = -1
        
        print(f"[{i*3}s] URL: {url[:70]} | HTML: {html_len} | Inputs: {inputs} | Buttons: {btns}")
        
        if inputs > 0 or btns > 0:
            break
    
    page.close()
    context.close()
