"""
Capture the complete signup flow: email → name → OTP → password.
Save all requests and responses for analysis.
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
    
    def handle_response(response):
        if '/api/execute' in response.url:
            body = ''
            try:
                body = response.json()
            except:
                body = response.text()
            captured.append({'type': 'response', 'url': response.url, 'status': response.status, 'body': body})
    
    def handle_request(route, request):
        if '/api/execute' in request.url:
            captured.append({'type': 'request', 'url': request.url, 'method': request.method, 'post_data': request.post_data})
        route.continue_()
    
    page.on('response', handle_response)
    page.route('**/*', handle_request)
    
    page.goto(signin_url, wait_until='domcontentloaded', timeout=60000)
    
    email = 'fulltest@havenhaus.in'
    
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
    
    # Wait for the flow to progress (name, OTP, password)
    # The SPA will handle all transitions automatically
    # We just need to interact at each step
    
    for step in range(60):
        time.sleep(2)
        body = ''
        try:
            body = page.evaluate('document.body.innerText')
        except:
            pass
        
        bt = body.lower()
        
        # Check current step
        if 'enter your name' in bt or ('name' in bt and len(bt) > 10 and 'email' not in bt):
            print(f"[{step*2}s] Name step: {body[:80]}")
            # Fill name
            try:
                name_input = page.locator('input[type="text"]').first
                if name_input.is_visible():
                    name_input.fill('Test User')
                    time.sleep(1)
                    name_input.press('Enter')
                    print("  Name submitted")
            except Exception as e:
                print(f"  Name error: {e}")
        
        elif 'verification code' in bt or ('code' in bt and ('enter' in bt or 'otp' in bt)):
            print(f"[{step*2}s] OTP step: {body[:80]}")
            # Try to get OTP from Gmail
            try:
                import imaplib
                mail = imaplib.IMAP4_SSL('imap.gmail.com')
                mail.login('anshika31618@gmail.com', 'hlcv eobi tfwh terw'.replace(' ', ''))
                mail.select('inbox')
                status, messages = mail.search(None, f'(TO "{email}")')
                otp = None
                if status == 'OK' and messages[0]:
                    msg_ids = messages[0].split()
                    for msg_id in reversed(msg_ids[-3:]):
                        status, msg_data = mail.fetch(msg_id, '(BODY.PEEK[])')
                        if status == 'OK':
                            raw = msg_data[0][1]
                            msg_body = raw.decode('utf-8', errors='ignore')
                            otp_match = re.search(r'\b(\d{6})\b', msg_body)
                            if otp_match:
                                otp = otp_match.group(1)
                                break
                mail.logout()
                
                if otp:
                    print(f"  OTP found: {otp}")
                    otp_input = page.locator('input[type="text"], input[name*="code"], input[autocomplete="one-time-code"]').first
                    if otp_input.is_visible():
                        otp_input.fill(otp)
                        time.sleep(1)
                        otp_input.press('Enter')
                        print("  OTP submitted")
                else:
                    print("  OTP not found yet")
            except Exception as e:
                print(f"  OTP error: {e}")
        
        elif 'password' in bt and ('create' in bt or 'enter' in bt or 'confirm' in bt):
            print(f"[{step*2}s] Password step: {body[:80]}")
            # Fill password
            try:
                password = 'TestPass123!@#'
                pw_inputs = page.locator('input[type="password"]').all()
                if len(pw_inputs) >= 2:
                    pw_inputs[0].fill(password)
                    time.sleep(0.5)
                    pw_inputs[1].fill(password)
                    time.sleep(1)
                    # Find submit button
                    btn = page.locator('button:has-text("Create"), button:has-text("Continue"), button:has-text("Submit")').first
                    if btn.is_visible():
                        btn.click()
                        print("  Password submitted")
                    else:
                        pw_inputs[1].press('Enter')
                        print("  Password submitted via Enter")
            except Exception as e:
                print(f"  Password error: {e}")
        
        elif 'success' in bt or 'welcome' in bt or 'signed in' in bt:
            print(f"[{step*2}s] SUCCESS: {body[:100]}")
            break
        
        elif 'err-837' in bt:
            print(f"[{step*2}s] ERR-837 BLOCKED!")
            break
        
        if step % 5 == 0 and step > 0:
            print(f"  [{step*2}s] body: {body[:60]}")
    
    # Check final state
    body = ''
    try:
        body = page.evaluate('document.body.innerText')
    except:
        pass
    print(f"\nFinal body: {body[:200]}")
    print(f"Final URL: {page.url[:100]}")
    
    browser.close()

# Save captured data
with open('/home/ubuntu/kiro-gen/full_signup_flow.json', 'w') as f:
    json.dump(captured, f, indent=2)

# Print summary
print(f"\n{'='*70}")
print(f"Total captured: {len(captured)} items")
for i, item in enumerate(captured):
    if item['type'] == 'request' and item.get('post_data'):
        body = json.loads(item['post_data'])
        step_id = body.get('stepId', 'N/A')
        action = body.get('actionId', '')
        action_str = f" action={action}" if action else ""
        print(f"  [{i}] REQ stepId={step_id}{action_str}")
    elif item['type'] == 'response':
        resp_body = item.get('body', {})
        if isinstance(resp_body, dict):
            resp_step = resp_body.get('stepId', 'N/A')
            resp_status = item.get('status', 0)
            wsh = resp_body.get('workflowStateHandle', '')[:20]
            redirect = resp_body.get('redirect', {})
            redirect_str = f" redirect={redirect.get('url', '')[:50]}" if redirect else ""
            error = resp_body.get('message', {}).get('errorCode', '') if isinstance(resp_body.get('message'), dict) else ''
            error_str = f" error={error}" if error else ""
            print(f"  [{i}] RESP status={resp_status} stepId={resp_step} wsh={wsh}...{redirect_str}{error_str}")
        else:
            print(f"  [{i}] RESP status={item.get('status', 0)} body={str(resp_body)[:50]}")
