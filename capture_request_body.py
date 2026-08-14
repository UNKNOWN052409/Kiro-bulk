"""
Use Playwright to navigate to the signin page and capture the exact request
body when the email is submitted. We'll use page.route() to intercept the
execute API call and log the full request.
"""

import uuid, secrets, hashlib, base64, requests, json, re, time, random, string
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
print(f"Client ID: {client_id}")

code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

# Get the signin URL
session = requests.Session()
session.headers.update({'User-Agent': UA})
resp = session.get(auth_url, allow_redirects=True, timeout=30)
start_url = resp.url

resp2 = session.get(
    'https://portal.sso.us-east-1.amazonaws.com/login',
    params={'directory_id': 'view', 'redirect_url': start_url},
    timeout=30
)
login_data = resp2.json()
signin_url = login_data['redirectUrl']
csrf_token = login_data['csrfToken']
print(f"Signin URL: {signin_url}")
print(f"CSRF Token: {csrf_token}")

# Now use Playwright to navigate and capture the request
from playwright.sync_api import sync_playwright

captured_requests = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1920,1080']
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent=UA,
        locale='en-US',
        ignore_https_errors=True,
    )
    
    # Set the CSRF cookie
    context.add_cookies([{
        'name': 'loginCsrfToken',
        'value': csrf_token,
        'domain': '.signin.aws',
        'path': '/',
        'secure': True,
        'sameSite': 'Lax'
    }])
    
    page = context.new_page()
    
    # Intercept all requests to capture the execute API call
    def handle_request(route, request):
        url = request.url
        if '/api/execute' in url or '/platform/' in url:
            captured = {
                'url': url,
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': request.post_data,
                'timestamp': time.time()
            }
            captured_requests.append(captured)
            print(f"\n[CAPTURED] {request.method} {url}")
            if request.post_data:
                print(f"  Body: {request.post_data[:500]}")
        route.continue_()
    
    page.route('**/*', handle_request)
    
    # Navigate to signin page
    print("\nNavigating to signin page...")
    page.goto(signin_url, wait_until='domcontentloaded', timeout=60000)
    
    # Wait for the form to load
    print("Waiting for form...")
    for i in range(30):
        time.sleep(1)
        body = ''
        try:
            body = page.evaluate('document.body.innerText')
        except:
            pass
        
        if 'email' in body.lower() or 'get started' in body.lower():
            print(f"  Form visible [{i}s]: {body[:100]}")
            break
        if i % 5 == 0 and i > 0:
            print(f"  [{i}s] body: {body[:60]}")
    
    # Fill email
    email = 'testcap@havenhaus.in'
    print(f"\nFilling email: {email}")
    try:
        # Find the email input
        email_input = page.locator('input[type="email"], input[name="username"], input[autocomplete="username"]').first
        if email_input.is_visible():
            email_input.fill(email)
            time.sleep(0.5)
            print("  Email filled")
            
            # Click Continue
            continue_btn = page.locator('button:has-text("Continue")').first
            if continue_btn.is_visible():
                continue_btn.click()
                print("  Continue clicked")
                
                # Wait for the API call
                time.sleep(3)
                print(f"\n  Captured {len(captured_requests)} requests")
            else:
                print("  Continue button not visible")
                # List visible buttons
                buttons = page.locator('button').all()
                for b in buttons[:10]:
                    try:
                        text = b.inner_text()
                        vis = b.is_visible()
                        print(f"    Button: '{text}' visible={vis}")
                    except:
                        pass
        else:
            print("  Email input not visible")
            # Try to find any input
            inputs = page.locator('input').all()
            for inp in inputs[:10]:
                try:
                    t = inp.get_attribute('type')
                    n = inp.get_attribute('name')
                    ph = inp.get_attribute('placeholder')
                    vis = inp.is_visible()
                    print(f"    Input: type={t} name={n} placeholder={ph} visible={vis}")
                except:
                    pass
    except Exception as e:
        print(f"  Error: {e}")
    
    # Save captured requests
    with open('/home/ubuntu/kiro-gen/captured_api_call.json', 'w') as f:
        json.dump(captured_requests, f, indent=2)
    print(f"\nSaved {len(captured_requests)} captured requests to captured_api_call.json")
    
    browser.close()
