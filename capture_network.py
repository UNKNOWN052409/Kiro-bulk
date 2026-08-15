#!/usr/bin/env python3
"""Navigate to signup page and capture ALL network requests."""
import time
import json
import uuid
import random
import secrets
import hashlib
import base64
from urllib.parse import urlparse, parse_qs, quote
from playwright.sync_api import sync_playwright
from curl_cffi import requests as cffi_requests

CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
DIRECTORY_ID = 'd-9067642ac7'
SIGNIN_BASE = f'https://us-east-1.signin.aws/platform/{DIRECTORY_ID}'

captured = []

def on_request(request):
    captured.append({'type': 'req', 'url': request.url, 'method': request.method, 'headers': dict(request.headers)})

def on_response(response):
    captured.append({'type': 'resp', 'url': response.url, 'status': response.status})

# OIDC register
reg = cffi_requests.post('https://oidc.us-east-1.amazonaws.com/client/register', json={
    'clientName': f'kiro-{uuid.uuid4().hex[:8]}',
    'clientType': 'public',
    'scopes': ['codewhisperer:completions', 'codewhisperer:analysis', 'codewhisperer:conversations'],
    'grantTypes': ['authorization_code', 'refresh_token'],
    'redirectUris': ['http://127.0.0.1:9997/oauth/callback'],
    'issuerUrl': 'https://view.awsapps.com/start'
})
client_id = reg.json()['clientId']

code_verifier = secrets.token_urlsafe(64)[:128]
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
auth_url = (f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code'
            f'&client_id={client_id}'
            f'&redirect_uri={quote("http://127.0.0.1:9997/oauth/callback")}'
            f'&scopes=codewhisperer%3Acompletions%20codewhisperer%3Aanalysis%20codewhisperer%3Aconversations'
            f'&state={secrets.token_urlsafe(16)}'
            f'&code_challenge={code_challenge}'
            f'&code_challenge_method=S256')

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context('/tmp/cap-profile', channel='chromium', headless=True,
        viewport={'width': 1920, 'height': 1080}, user_agent=CHROME_UA, locale='en-US',
        proxy={'server': 'http://127.0.0.1:8899'}, args=['--no-sandbox'])
    pg = ctx.pages[0]
    pg.on('request', on_request)
    pg.on('response', on_response)
    
    # Navigate through OIDC - wait for redirect to signin.aws
    pg.goto(auth_url, wait_until='load', timeout=120000)
    # Wait for the JS redirect from awsapps.com to signin.aws
    try:
        pg.wait_for_url('**/signin.aws**', timeout=30000)
    except:
        print('Warning: redirect to signin.aws did not happen')
    time.sleep(3)  # Extra wait for page stabilization
    qs = parse_qs(urlparse(pg.url).query)
    ws = qs.get('workflowStateHandle', [''])[0]
    print(f'URL: {pg.url[:120]}')
    print(f'WS: {ws}')
    
    FP = {'browser': 'Chrome', 'version': '124.0.0.0', 'os': 'Windows'}
    
    # Init
    js = f"""(async () => {{
        const resp = await fetch('{SIGNIN_BASE}/api/execute', {{method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{stepId: '', workflowStateHandle: '{ws}', actionId: '', inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {json.dumps(FP)}}}], visitorId: crypto.randomUUID(), requestId: crypto.randomUUID()}})
        }});
        let d = {{}}; try {{ d = await resp.json(); }} catch(e) {{}}
        return JSON.stringify({{status: resp.status, ws: d.workflowStateHandle, step: d.stepId, fullData: d}});
    }})()"""
    r = json.loads(pg.evaluate(js))
    ws = r.get('ws', ws)
    print(f'Init: {json.dumps(r)}')
    time.sleep(2)
    
    # Email form
    js = f"""(async () => {{
        const resp = await fetch('{SIGNIN_BASE}/api/execute', {{method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{stepId: 'start', workflowStateHandle: '{ws}', actionId: '', inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {json.dumps(FP)}}}], visitorId: crypto.randomUUID(), requestId: crypto.randomUUID()}})
        }});
        let d = {{}}; try {{ d = await resp.json(); }} catch(e) {{}}
        return JSON.stringify({{status: resp.status, ws: d.workflowStateHandle, step: d.stepId}});
    }})()"""
    r = json.loads(pg.evaluate(js))
    ws = r.get('ws', ws)
    print(f'EmailForm: {r}')
    time.sleep(2)
    
    # Submit email
    email = f'cap{random.randint(10000,99999)}@havenhaus.in'
    js = f"""(async () => {{
        const resp = await fetch('{SIGNIN_BASE}/api/execute', {{method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{stepId: 'get-identity-user', workflowStateHandle: '{ws}', actionId: 'SIGNUP', inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {json.dumps(FP)}}}, {{input_type: 'UserRequestInput', identity: '{email}'}}], visitorId: crypto.randomUUID(), requestId: crypto.randomUUID()}})
        }});
        let d = {{}}; try {{ d = await resp.json(); }} catch(e) {{}}
        return JSON.stringify({{status: resp.status, ws: d.workflowStateHandle, step: d.stepId, redirect: d.message?.continueUrl || ''}});
    }})()"""
    r = json.loads(pg.evaluate(js))
    ws = r.get('ws', ws)
    redirect = r.get('redirect', '')
    print(f'Email: {r}')
    time.sleep(2)
    
    # NOW: Navigate to the signup page
    if not redirect:
        redirect = f'{SIGNIN_BASE}/signup?workflowStateHandle={ws}'
    print(f'\nNavigating to signup: {redirect[:100]}')
    
    # Clear captured requests
    captured.clear()
    
    pg.goto(redirect, wait_until='load', timeout=60000)
    time.sleep(10)  # Wait for the page to fully load and make its API calls
    
    print(f'\nOn page: {pg.url[:100]}')
    print(f'\n=== Captured requests to execute/api endpoints ===')
    for c in captured:
        url = c.get('url', '')
        if 'execute' in url or '/api/' in url:
            if c['type'] == 'req':
                print(f"  REQ [{c['method']}] {url}")
            else:
                print(f"  RESP [{c['status']}] {url}")
    
    # Also print all requests to signin.aws
    print(f'\n=== All signin.aws requests ===')
    for c in captured:
        url = c.get('url', '')
        if 'signin.aws' in url and c['type'] == 'req':
            print(f"  [{c['method']}] {url[:150]}")
    
    # Try to get the page's internal state
    print(f'\n=== Page resources ===')
    resources = pg.evaluate("() => performance.getEntriesByType('resource').map(r => r.name).filter(n => n.includes('execute') || n.includes('api') || n.includes('platform'))")
    for res in resources:
        print(f"  {res[:150]}")
    
    ctx.close()

print('\nDone!')
