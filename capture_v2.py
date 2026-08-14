"""
Capture the complete signup flow with fixes for response errors.
"""

import uuid, secrets, hashlib, base64, requests, json, time, re
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
            captured.append({'type': 'request', 'post_data': request.post_data})
        route.continue_()
    
    def handle_response(response):
        if '/api/execute' in response.url:
            try:
                body = response.json()
                captured.append({'type': 'response', 'status': response.status, 'body': body})
            except:
                # Response body not available for navigated-away responses
                captured.append({'type': 'response', 'status': response.status, 'body': 'NAVIGATED_AWAY'})
    
    page.on('response', handle_response)
    page.route('**/*', handle_request)
    
    page.goto(signin_url, wait_until='domcontentloaded', timeout=60000)
    
    email = 'flowtest@havenhaus.in'
    
    # Wait for email form
    for i in range(30):
        time.sleep(1)
        try:
            body = page.evaluate('document.body.innerText')
            if 'email' in body.lower() and 'continue' in body.lower():
                print(f"[{i}s] Email form ready")
                break
        except:
            pass
    
    # Submit email
    page.locator('input[type="email"]').first.fill(email)
    time.sleep(0.5)
    page.locator('button:has-text("Continue")').first.click()
    print("Email submitted")
    
    # Wait and handle name step
    for step in range(30):
        time.sleep(2)
        body = ''
        try:
            body = page.evaluate('document.body.innerText')
        except:
            pass
        
        bt = body.lower()
        
        if 'enter your name' in bt or ('name' in bt and 'email' not in bt[:50]):
            print(f"[{step*2}s] Name step detected")
            try:
                name_input = page.locator('input[type="text"]').first
                if name_input.is_visible():
                    name_input.fill('Test User')
                    time.sleep(1)
                    name_input.press('Enter')
                    print("  Name submitted")
            except Exception as e:
                print(f"  Name error: {e}")
        
        elif 'otp' in bt or ('code' in bt and 'verification' in bt):
            print(f"[{step*2}s] OTP step detected")
            # Don't submit OTP - just capture the flow up to here
            break
        
        if step % 5 == 0:
            print(f"  [{step*2}s] body: {body[:60]}")
    
    browser.close()

# Save
with open('/home/ubuntu/kiro-gen/full_signup_flow.json', 'w') as f:
    json.dump(captured, f, indent=2)

# Print summary
print(f"\n{'='*60}")
print(f"Total: {len(captured)}")
for i, item in enumerate(captured):
    if item['type'] == 'request':
        body = json.loads(item['post_data']) if item.get('post_data') else {}
        step = body.get('stepId', 'N/A')
        action = body.get('actionId', '')
        inputs = [inp.get('input_type', '').replace('RequestInput', '') for inp in body.get('inputs', [])]
        print(f"[{i:2d}] REQ  {step:20s} {action:8s} [{', '.join(inputs)}]")
    else:
        body = item.get('body', {})
        if isinstance(body, dict):
            step = body.get('stepId', 'N/A')
            err = body.get('message', {}).get('errorCode', '') if isinstance(body.get('message'), dict) else ''
            wsh = body.get('workflowStateHandle', '')[:15]
            red = body.get('redirect', {})
            red_url = red.get('url', '')[:40] if red else ''
            print(f"[{i:2d}] RESP {item['status']:3d} {step:20s} err={err:20s} wsh={wsh:15s} red={red_url}")
        else:
            print(f"[{i:2d}] RESP {item['status']:3d} {body}")
