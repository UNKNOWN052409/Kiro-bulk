from playwright.sync_api import sync_playwright
import time, uuid, secrets, hashlib, base64, requests

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis"]

# Register OIDC client
reg_payload = {
    "clientName": f"test-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9998/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

# PKCE
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = 'http://127.0.0.1:9998/oauth/callback'
auth_url = f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scopes={scopes_encoded}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256'

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
    )
    context = browser.new_context(viewport={'width': 1280, 'height': 720})
    page = context.new_page()
    
    # Navigate to OIDC authorize URL (NO proxy)
    print("  Navigating to OIDC authorize URL (no proxy)...")
    try:
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
    except:
        pass
    
    # Wait for sign-in page
    for i in range(15):
        time.sleep(2)
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            url = page.url
            if 'email' in body.lower() and 'continue' in body.lower():
                print(f"  Sign-in page loaded! URL: {url[:80]}")
                break
        except:
            pass
    
    # Enter a test email
    print("  Entering test email...")
    try:
        inputs = page.locator('input').all()
        visible = [inp for inp in inputs if inp.is_visible()]
        if visible:
            visible[0].fill('test123@havenhaus.in')
            time.sleep(1)
            btn = page.get_by_role("button", name="Continue")
            if btn.is_visible():
                btn.click()
                print("  Email submitted!")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Wait for redirect to profile.aws.amazon.com
    print("  Waiting for redirect to profile.aws.amazon.com...")
    for i in range(30):
        time.sleep(2)
        try:
            url = page.url
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            print(f"  [{i*2}s] url={url[:100]} body_len={len(body)}")
            if len(body) > 100:
                print(f"    Body: {body[:200]}")
                break
        except:
            pass
    
    browser.close()
