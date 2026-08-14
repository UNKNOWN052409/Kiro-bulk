"""
Debug the email submission - check page state after clicking Continue.
"""

import uuid, secrets, hashlib, base64, requests, json, time
from urllib.parse import quote

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]
CALLBACK_PORT = 9997
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

# Register OIDC client
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": [f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

session = requests.Session()
session.headers.update({'User-Agent': UA})
resp = session.get(auth_url, allow_redirects=True, timeout=30)
start_url = resp.url
resp2 = session.get('https://portal.sso.us-east-1.amazonaws.com/login',
                    params={'directory_id': 'view', 'redirect_url': start_url}, timeout=30)
login_data = resp2.json()
signin_url = login_data['redirectUrl']
csrf_token = login_data['csrfToken']

captured = []

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
    context = browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=UA, locale='en-US', ignore_https_errors=True)
    context.add_cookies([{'name': 'loginCsrfToken', 'value': csrf_token, 'domain': '.signin.aws', 'path': '/', 'secure': True, 'sameSite': 'Lax'}])
    page = context.new_page()
    
    def handle_request(route, request):
        if '/api/execute' in request.url:
            captured.append({'url': request.url, 'method': request.method, 'post_data': request.post_data})
            print(f"  [CAPTURED] {request.method} /api/execute body: {request.post_data[:100] if request.post_data else 'N/A'}")
        route.continue_()
    
    page.route('**/*', handle_request)
    page.goto(signin_url, wait_until='domcontentloaded', timeout=60000)
    
    # Wait for form
    for i in range(30):
        time.sleep(1)
        try:
            body = page.evaluate('document.body.innerText')
            if 'email' in body.lower() and 'continue' in body.lower():
                print(f"Form ready [{i}s]")
                break
        except:
            pass
    
    # Check what inputs are available
    print("\nAvailable inputs:")
    inputs_info = page.evaluate("""
        () => {
            const inputs = document.querySelectorAll('input');
            return Array.from(inputs).map(i => ({
                type: i.type,
                name: i.name,
                id: i.id,
                placeholder: i.placeholder,
                autocomplete: i.autocomplete,
                visible: i.offsetParent !== null
            }));
        }
    """)
    for inp in inputs_info:
        print(f"  {json.dumps(inp)}")
    
    # Fill email using JavaScript
    email = 'debugtest@havenhaus.in'
    print(f"\nFilling email: {email}")
    
    # Try different approaches
    # Approach 1: Fill via locator
    email_input = page.locator('input[type="email"]').first
    if email_input.is_visible():
        print("  Found email input via type=email")
        email_input.fill(email)
    else:
        # Try by name
        email_input = page.locator('input[name="username"]').first
        if email_input.is_visible():
            print("  Found email input via name=username")
            email_input.fill(email)
        else:
            # Try any visible input
            email_input = page.locator('input:visible').first
            print("  Using first visible input")
            email_input.fill(email)
    
    # Verify the value was set
    val = page.evaluate("(() => { const el = document.querySelector('input[type=\"email\"]'); return el ? el.value : null; })()")
    print(f"  Input value after fill: {val}")
    
    # Click Continue - try multiple approaches
    print("\nTrying to click Continue...")
    
    # Approach 1: Click via locator
    try:
        btn = page.locator('button:has-text("Continue")').first
        if btn.is_visible():
            btn.click()
            print("  Clicked via button:has-text('Continue')")
        else:
            print("  Button not visible via has-text")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Wait and check page state
    print("\nWaiting 5s...")
    time.sleep(5)
    
    # Check page state
    body = ''
    try:
        body = page.evaluate('document.body.innerText')
    except:
        pass
    print(f"  Body: {body[:200]}")
    print(f"  URL: {page.url[:100]}")
    print(f"  Captured: {len(captured)} requests")
    
    # If no capture, the email submission didn't fire
    # Let's try pressing Enter on the input instead
    if len(captured) == 0:
        print("\n  No POST captured. Trying Enter key...")
        email_input.press('Enter')
        time.sleep(5)
        body = ''
        try:
            body = page.evaluate('document.body.innerText')
        except:
            pass
        print(f"  Body after Enter: {body[:200]}")
        print(f"  Captured: {len(captured)} requests")
    
    browser.close()

print(f"\nTotal captured: {len(captured)}")
for i, c in enumerate(captured):
    if c.get('post_data'):
        body = json.loads(c['post_data'])
        for inp in body.get('inputs', []):
            if 'fingerPrint' in inp:
                inp['fingerPrint'] = inp['fingerPrint'][:50] + '...'
        print(f"\n=== Request {i} ===")
        print(json.dumps(body, indent=2))
