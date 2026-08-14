"""
Capture both requests AND responses to understand the full state machine.
We need to see what the start step returns (next workflowStateHandle)
and what the email submission returns.
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
    
    def handle_response(response):
        if '/api/execute' in response.url:
            body = ''
            try:
                body = response.json()
            except:
                body = response.text()
            captured.append({
                'type': 'response',
                'url': response.url,
                'status': response.status,
                'body': body,
            })
    
    def handle_request(route, request):
        if '/api/execute' in request.url:
            captured.append({
                'type': 'request',
                'url': request.url,
                'method': request.method,
                'post_data': request.post_data,
            })
        route.continue_()
    
    page.on('response', handle_response)
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
    email_input.fill('resptest@havenhaus.in')
    time.sleep(1)
    btn = page.locator('button:has-text("Continue")').first
    btn.click()
    print("Submitted email, waiting...")
    time.sleep(5)
    
    # Check what happened
    body = ''
    try:
        body = page.evaluate('document.body.innerText')
    except:
        pass
    print(f"\nPage body after submit: {body[:100]}")
    
    # Wait more for OTP page
    print("Waiting for next page...")
    for i in range(30):
        time.sleep(2)
        body = ''
        try:
            body = page.evaluate('document.body.innerText')
        except:
            pass
        if 'code' in body.lower() and ('enter' in body.lower() or 'verification' in body.lower()):
            print(f"  OTP page at [{i*2}s]: {body[:100]}")
            break
    
    browser.close()

# Print all captured data
print(f"\n{'='*70}")
print(f"Total captured: {len(captured)}")
for i, item in enumerate(captured):
    print(f"\n=== Item {i} ({item['type']}) ===")
    if item['type'] == 'request':
        body = json.loads(item['post_data']) if item.get('post_data') else {}
        # Truncate fingerprint
        for inp in body.get('inputs', []):
            if 'fingerPrint' in inp:
                inp['fingerPrint'] = inp['fingerPrint'][:40] + '...'
        print(f"  Method: {item['method']}")
        print(f"  Body: {json.dumps(body, indent=2)[:800]}")
    else:
        resp_body = item['body']
        if isinstance(resp_body, dict):
            # Truncate any long strings
            def truncate(obj, max_len=100):
                if isinstance(obj, dict):
                    return {k: truncate(v, max_len) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [truncate(v, max_len) for v in obj]
                elif isinstance(obj, str) and len(obj) > max_len:
                    return obj[:max_len] + '...TRUNCATED'
                return obj
            resp_body = truncate(resp_body)
        print(f"  Status: {item['status']}")
        print(f"  Body: {json.dumps(resp_body, indent=2)[:1000]}")
