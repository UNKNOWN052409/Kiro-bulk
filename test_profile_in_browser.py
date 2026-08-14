#!/usr/bin/env python3
"""
Use Playwright page.evaluate() to make profile.aws.amazon.com API calls
from within the browser context (same session, cookies, TLS fingerprint).
This avoids the ERR-837 issue because the browser's real TLS fingerprint is used.
"""

import uuid, secrets, hashlib, base64, requests, random, string, json, re, time
from urllib.parse import quote

REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]

def generate_email():
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}@havenhaus.in"

email_addr = generate_email()
print(f"Email: {email_addr}")

# Register OIDC client (no proxy needed)
reg_payload = {
    "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
    "clientType": "public",
    "scopes": GRANT_SCOPES,
    "grantTypes": ["authorization_code", "refresh_token"],
    "redirectUris": ["http://127.0.0.1:9997/oauth/callback"],
    "issuerUrl": ISSUER_URL
}
reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
client_id = reg_resp.json()['clientId']

# PKCE
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
scopes_encoded = ' '.join(GRANT_SCOPES)
state = secrets.token_urlsafe(16)
redirect_uri = 'http://127.0.0.1:9997/oauth/callback'
auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
            f'&redirect_uri={quote(redirect_uri)}&scopes={quote(scopes_encoded)}'
            f'&state={state}&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

print(f"\n[Browser] Navigating through sign-in flow...")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    )
    page = browser.new_page()
    
    try:
        # Navigate to auth URL
        page.goto(auth_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)
        
        # Fill email
        email_input = page.locator('input[type="email"]').first
        email_input.fill(email_addr)
        time.sleep(1)
        
        # Click Continue
        page.locator('button:has-text("Continue")').first.click()
        time.sleep(5)
        
        # Click Sign up / Get started
        for selector in ['button:has-text("Sign up")', 'button:has-text("Create account")', 'button:has-text("Get started")']:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click()
                    print(f"  Clicked: {selector}")
                    break
            except:
                pass
        
        time.sleep(3)
        print(f"  URL: {page.url[:120]}")
        
        # Wait for profile.aws.amazon.com with workflowID
        workflow_id = None
        for i in range(10):
            time.sleep(1)
            url = page.url
            if 'profile.aws.amazon.com' in url and 'workflowID=' in url:
                raw = url.split('workflowID=')[1]
                workflow_id = raw.split('#')[0].split('&')[0]
                if re.match(r'[0-9a-f-]{36}$', workflow_id):
                    print(f"  FOUND workflowID: {workflow_id}")
                    break
        
        if workflow_id:
            # Now make API calls from within the browser context
            print("\n[In-Browser API] Making API calls via page.evaluate()...")
            
            # get-config
            config_result = page.evaluate('''
                async () => {
                    const resp = await fetch('/api/get-config', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json;charset=UTF-8'},
                        body: JSON.stringify({})
                    });
                    return {status: resp.status, body: await resp.text()};
                }
            ''')
            print(f"  get-config: HTTP {config_result['status']}")
            print(f"    Response: {config_result['body'][:200]}")
            
            # get-app-context
            ctx_result = page.evaluate('''
                async (wid) => {
                    const resp = await fetch('/api/get-app-context', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json;charset=UTF-8'},
                        body: JSON.stringify({workflowID: wid})
                    });
                    return {status: resp.status, body: await resp.text()};
                }
            ''', workflow_id)
            print(f"  get-app-context: HTTP {ctx_result['status']}")
            print(f"    Response: {ctx_result['body'][:200]}")
            
            # Generate fingerprint using browser's own method
            # The SPA generates a fingerprint - let's try using a simple one
            # or use the one we captured earlier
            with open('/home/ubuntu/kiro-gen/profile_fingerprint.txt', 'r') as f:
                fp = f.read().strip()
            
            # start
            start_result = page.evaluate('''
                async (params) => {
                    const resp = await fetch('/api/start', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json;charset=UTF-8'},
                        body: JSON.stringify({
                            workflowID: params.workflowID,
                            browserData: {
                                attributes: {
                                    fingerprint: params.fingerprint,
                                    eventTimestamp: params.timestamp,
                                    timeSpentOnPage: "44",
                                    eventType: "PageLoad",
                                    ubid: params.ubid
                                },
                                cookies: {}
                            }
                        })
                    });
                    return {status: resp.status, body: await resp.text()};
                }
            ''', {
                'workflowID': workflow_id,
                'fingerprint': fp,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()) + f".{random.randint(0,999):03d}Z",
                'ubid': f"{random.randint(100,999)}-{random.randint(1000000,9999999)}-{random.randint(1000000,9999999)}"
            })
            print(f"  start: HTTP {start_result['status']}")
            print(f"    Response: {start_result['body'][:500]}")
            
            if start_result['status'] == 200:
                try:
                    start_data = json.loads(start_result['body'])
                    workflow_state = start_data.get('workflowState') or start_data.get('state')
                    print(f"    workflowState: {workflow_state}")
                    
                    if workflow_state:
                        # send-otp
                        otp_result = page.evaluate('''
                            async (params) => {
                                const resp = await fetch('/api/send-otp', {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json;charset=UTF-8'},
                                    body: JSON.stringify({
                                        workflowState: params.workflowState,
                                        email: params.email,
                                        browserData: {
                                            attributes: {
                                                fingerprint: params.fingerprint,
                                                eventTimestamp: params.timestamp,
                                                timeSpentOnPage: "10",
                                                eventType: "OTPRequest",
                                                ubid: params.ubid
                                            },
                                            cookies: {}
                                        }
                                    })
                                });
                                return {status: resp.status, body: await resp.text()};
                            }
                        ''', {
                            'workflowState': workflow_state,
                            'email': email_addr,
                            'fingerprint': fp,
                            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()) + f".{random.randint(0,999):03d}Z",
                            'ubid': f"{random.randint(100,999)}-{random.randint(1000000,9999999)}-{random.randint(1000000,9999999)}"
                        })
                        print(f"  send-otp: HTTP {otp_result['status']}")
                        print(f"    Response: {otp_result['body'][:300]}")
                except Exception as e:
                    print(f"    Error parsing start response: {e}")
        
        browser.close()
    except Exception as e:
        print(f"  Error: {e}")
        browser.close()

print(f"\n{'='*60}")
