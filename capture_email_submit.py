"""
Capture the email submission request body with a longer wait.
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

# Get signin URL
session = requests.Session()
session.headers.update({'User-Agent': UA})
resp = session.get(auth_url, allow_redirects=True, timeout=30)
start_url = resp.url
resp2 = session.get('https://portal.sso.us-east-1.amazonaws.com/login',
                    params={'directory_id': 'view', 'redirect_url': start_url}, timeout=30)
login_data = resp2.json()
signin_url = login_data['redirectUrl']
csrf_token = login_data['csrfToken']
print(f"Signin URL: {signin_url}")

captured = []

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-dev-shm-usage'])
    context = browser.new_context(viewport={'width': 1920, 'height': 1080}, user_agent=UA, locale='en-US', ignore_https_errors=True)
    context.add_cookies([{'name': 'loginCsrfToken', 'value': csrf_token, 'domain': '.signin.aws', 'path': '/', 'secure': True, 'sameSite': 'Lax'}])
    page = context.new_page()
    
    def handle_request(route, request):
        if '/api/execute' in request.url:
            captured.append({
                'url': request.url, 'method': request.method,
                'headers': {k: v for k, v in request.headers.items() if k.lower() not in ['host']},
                'post_data': request.post_data,
            })
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
    
    # Fill email and submit
    email_input = page.locator('input[type="email"]').first
    if email_input.is_visible():
        email_input.fill('capttest2@havenhaus.in')
        time.sleep(1)
        btn = page.locator('button:has-text("Continue")').first
        if btn.is_visible():
            btn.click()
            print("Continue clicked, waiting 5s...")
            time.sleep(5)
    
    print(f"\nCaptured {len(captured)} execute requests")
    
    for i, req in enumerate(captured):
        if req.get('post_data'):
            body = json.loads(req['post_data'])
            # Truncate fingerprint
            for inp in body.get('inputs', []):
                if 'fingerPrint' in inp:
                    inp['fingerPrint'] = inp['fingerPrint'][:60] + '...TRUNCATED'
            print(f"\n=== Request {i}: stepId={body.get('stepId')}, requestId={body.get('requestId')} ===")
            print(json.dumps(body, indent=2))
    
    browser.close()

# Save full data
with open('/home/ubuntu/kiro-gen/captured_email_body.json', 'w') as f:
    json.dump(captured, f, indent=2)
print(f"\nSaved to captured_email_body.json")
