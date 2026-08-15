#!/usr/bin/env python3
"""Debug the signup page by capturing its network requests."""
import time
import json
import random
import uuid
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

SIGNIN_BASE = 'https://us-east-1.signin.aws/platform/d-9067642ac7'
CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

# Use curl_cffi for OIDC registration (no proxy needed for this part)
from curl_cffi import requests as cffi_requests

print("[1] OIDC Register...")
reg = cffi_requests.post('https://oidc.us-east-1.amazonaws.com/client/register', json={
    'clientName': f'kiro-{uuid.uuid4().hex[:8]}',
    'clientType': 'public',
    'scopes': ['codewhisperer:completions', 'codewhisperer:analysis', 'codewhisperer:conversations'],
    'grantTypes': ['authorization_code', 'refresh_token'],
    'redirectUris': ['http://127.0.0.1:9997/oauth/callback'],
    'issuerUrl': 'https://view.awsapps.com/start'
})
client_id = reg.json()['clientId']
print(f"    Client ID: {client_id}")

import secrets, hashlib, base64
from urllib.parse import quote
code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b'=').decode()
scopes = 'codewhisperer:completions codewhisperer:analysis codewhisperer:conversations'
auth_url = (f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code'
            f'&client_id={client_id}'
            f'&redirect_uri={quote("http://127.0.0.1:9997/oauth/callback")}'
            f'&scopes={quote(scopes)}'
            f'&state={secrets.token_urlsafe(16)}'
            f'&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

# Network capture
captured_requests = []
captured_responses = []

def on_request(request):
    captured_requests.append({
        'url': request.url,
        'method': request.method,
        'headers': dict(request.headers),
    })

def on_response(response):
    url = response.url
    if 'execute' in url or 'api' in url:
        try:
            body = response.text()
            captured_responses.append({
                'url': url,
                'status': response.status,
                'body': body[:1000],
            })
            print(f"  RESP [{response.status}] {url[:150]}")
            if body:
                print(f"    Body: {body[:200]}")
        except:
            pass

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        '/tmp/debug2-profile',
        channel='chromium',
        headless=True,
        viewport={'width': 1920, 'height': 1080},
        user_agent=CHROME_UA,
        locale='en-US',
        timezone_id='America/New_York',
        proxy={'server': 'http://127.0.0.1:8899'},
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled'],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.on('request', on_request)
    page.on('response', on_response)
    
    # Navigate to OIDC authorize
    print("\n[2] Navigate to OIDC authorize...")
    page.goto(auth_url, wait_until='load', timeout=120000)
    print(f"    URL: {page.url[:150]}")
    
    # Get workflow state
    parsed = urlparse(page.url)
    qs = parse_qs(parsed.query)
    ws = qs.get('workflowStateHandle', [''])[0]
    print(f"    WS: {ws}")
    
    time.sleep(2)
    
    # Init
    print("\n[3] Init...")
    fingerprint = {"browser": "Chrome", "version": "124.0.0.0", "os": "Windows"}
    js_code = f"""
    (async () => {{
        const resp = await fetch('{SIGNIN_BASE}/api/execute', {{
            method: 'POST',
            credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                workflowStateHandle: '{ws}',
                stepId: '',
                actionId: '',
                inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}}]
            }})
        }});
        const data = await resp.json();
        return JSON.stringify({{status: resp.status, step: data.stepId, ws: data.workflowStateHandle}});
    }})()
    """
    result = page.evaluate(js_code)
    print(f"    Init: {result}")
    init_data = json.loads(result)
    ws = init_data.get('ws', ws)
    print(f"    Updated WS: {ws}")
    time.sleep(2)
    
    # Load email form
    print("\n[4] Load email form...")
    js_code = f"""
    (async () => {{
        const resp = await fetch('{SIGNIN_BASE}/api/execute', {{
            method: 'POST',
            credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                workflowStateHandle: '{ws}',
                stepId: 'start',
                actionId: '',
                inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}}]
            }})
        }});
        const data = await resp.json();
        return JSON.stringify({{status: resp.status, step: data.stepId, ws: data.workflowStateHandle, actions: data.actionIdList}});
    }})()
    """
    result = page.evaluate(js_code)
    print(f"    Email form: {result}")
    email_data = json.loads(result)
    ws = email_data.get('ws', ws)
    time.sleep(2)
    
    # Submit email
    email = f'test{random.randint(10000,99999)}@havenhaus.in'
    print(f"\n[5] Submit email: {email}")
    js_code = f"""
    (async () => {{
        const resp = await fetch('{SIGNIN_BASE}/api/execute', {{
            method: 'POST',
            credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                workflowStateHandle: '{ws}',
                stepId: 'get-identity-user',
                actionId: 'SIGNUP',
                inputs: [
                    {{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}},
                    {{input_type: 'UserRequestInput', identity: '{email}'}}
                ]
            }})
        }});
        const data = await resp.json();
        return JSON.stringify({{
            status: resp.status, step: data.stepId, ws: data.workflowStateHandle,
            redirect: data.message?.continueUrl || data.continueUrl || '',
            all: JSON.stringify(data).slice(0, 500)
        }});
    }})()
    """
    result = page.evaluate(js_code)
    print(f"    Email submit: {result}")
    email_submit = json.loads(result)
    
    # Get the signup redirect URL
    redirect_url = email_submit.get('redirect', '')
    if not redirect_url:
        # Try to get it from the full response
        all_data = email_submit.get('all', '')
        if 'signup' in all_data:
            import re
            m = re.search(r'https://[^"\\]+', all_data)
            if m:
                redirect_url = m.group(0)
    print(f"    Redirect: {redirect_url}")
    
    if redirect_url:
        # Extract the signup WS
        signup_ws = ''
        if 'workflowStateHandle=' in redirect_url:
            signup_ws = redirect_url.split('workflowStateHandle=')[1]
        print(f"    Signup WS: {signup_ws}")
        
        # NOW: Navigate to the signup page
        print(f"\n[6] Navigate to signup page...")
        page.goto(redirect_url, wait_until='load', timeout=60000)
        time.sleep(8)
        print(f"    On page: {page.url[:150]}")
        
        # Wait and see what requests the page makes
        time.sleep(3)
        
        # Try to make the same API call that the page would make
        print(f"\n[7] Try fetch from signup page...")
        js_code = f"""
        (async () => {{
            const results = [];
            
            // Try the signup API with the signup WS and stepId=''
            try {{
                const resp = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        workflowStateHandle: '{signup_ws}',
                        stepId: '',
                        actionId: '',
                        inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}}]
                    }})
                }});
                let data = {{}};
                try {{ data = await resp.json(); }} catch(e) {{}}
                results.push({{endpoint: 'init with signup ws', status: resp.status, step: data.stepId, ws: data.workflowStateHandle, actions: data.actionIdList, err: data.message?.text || ''}});
            }} catch(e) {{ results.push({{endpoint: 'init with signup ws', error: e.message}}); }}
            
            // Try with a fresh UUID as WS
            const freshWs = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
            try {{
                const resp2 = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        workflowStateHandle: freshWs,
                        stepId: '',
                        actionId: '',
                        inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}}]
                    }})
                }});
                let data2 = {{}};
                try {{ data2 = await resp2.json(); }} catch(e) {{}}
                results.push({{endpoint: 'init with fresh ws', status: resp2.status, step: data2.stepId, ws: data2.workflowStateHandle, actions: data2.actionIdList, err: data2.message?.text || ''}});
                
                // If init succeeded, try to get the next step
                if (data2.workflowStateHandle && data2.stepId) {{
                    const resp3 = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            workflowStateHandle: data2.workflowStateHandle,
                            stepId: 'start',
                            actionId: '',
                            inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}}]
                        }})
                    }});
                    let data3 = {{}};
                    try {{ data3 = await resp3.json(); }} catch(e) {{}}
                    results.push({{endpoint: 'step after init', status: resp3.status, step: data3.stepId, actions: data3.actionIdList, err: data3.message?.text || ''}});
                    
                    // Try to submit with SUBMIT action on whatever step we got
                    if (data3.stepId) {{
                        const resp4 = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                            method: 'POST',
                            credentials: 'include',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{
                                workflowStateHandle: data3.workflowStateHandle,
                                stepId: data3.stepId,
                                actionId: 'SUBMIT',
                                inputs: [
                                    {{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}},
                                    {{input_type: 'TextInput', key: 'verifiedUserName', value: 'Test User'}}
                                ]
                            }})
                        }});
                        let data4 = {{}};
                        try {{ data4 = await resp4.json(); }} catch(e) {{}}
                        results.push({{endpoint: 'submit with SUBMIT', status: resp4.status, step: data4.stepId, err: data4.message?.text || ''}});
                    }}
                }}
            }} catch(e) {{ results.push({{endpoint: 'fresh ws', error: e.message}}); }}
            
            return JSON.stringify(results);
        }})()
        """
        result = page.evaluate(js_code)
        print(f"    Results:\n{json.dumps(json.loads(result), indent=2)}")
        
        time.sleep(2)
    
    # Print captured requests
    print(f"\n\n=== Captured API Requests ===")
    for r in captured_requests:
        if 'execute' in r['url'] or 'api' in r['url']:
            print(f"  [{r['method']}] {r['url']}")
    
    print(f"\n=== Captured Responses ===")
    for r in captured_responses:
        print(f"  [{r['status']}] {r['url'][:100]}")
        print(f"    {r['body'][:200]}")
    
    context.close()

print("\nDone!")
