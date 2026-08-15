#!/usr/bin/env python3
"""Navigate to signup page and interact with the form directly."""
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

FP = {'browser': 'Chrome', 'version': '124.0.0.0', 'os': 'Windows'}

def api_call(page, step_id, ws, inputs, action_id='', api_path='/api/execute'):
    for attempt in range(5):
        try:
            js = f"""(async () => {{
                const resp = await fetch('{SIGNIN_BASE}{api_path}', {{method: 'POST', credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{stepId: '{step_id}', workflowStateHandle: '{ws}', actionId: '{action_id}', inputs: {json.dumps(inputs)}, visitorId: crypto.randomUUID(), requestId: crypto.randomUUID()}})
                }});
                let d = {{}}; try {{ d = await resp.json(); }} catch(e) {{}}
                return JSON.stringify({{status: resp.status, ws: d.workflowStateHandle, step: d.stepId, actions: d.actionIdList || [], full: d}});
            }})()"""
            return json.loads(page.evaluate(js))
        except Exception as e:
            if attempt < 4:
                time.sleep(3 + attempt * 2)
            else:
                return {'status': 0, 'error': str(e)}
    return {'status': 0, 'error': 'Max retries'}

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context('/tmp/interact-profile', channel='chromium', headless=True,
        viewport={'width': 1920, 'height': 1080}, user_agent=CHROME_UA, locale='en-US',
        timezone_id='America/New_York',
        proxy={'server': 'http://127.0.0.1:8899'}, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
    pg = ctx.pages[0]
    
    # Navigate through OIDC
    pg.goto(auth_url, wait_until='load', timeout=120000)
    try:
        pg.wait_for_url('**signin.aws**workflowStateHandle**', timeout=90000)
    except:
        for i in range(30):
            time.sleep(1)
            if 'signin.aws' in pg.url and 'workflowStateHandle' in pg.url:
                break
    
    qs = parse_qs(urlparse(pg.url).query)
    ws = qs.get('workflowStateHandle', [''])[0]
    print(f'WS: {ws}')
    time.sleep(3)
    
    # Init
    r = api_call(pg, '', ws, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP}])
    print(f'Init: status={r.get("status")}, step={r.get("step")}')
    ws = r.get('ws', ws)
    time.sleep(2)
    
    # Email form
    r = api_call(pg, 'start', ws, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP}])
    print(f'EmailForm: status={r.get("status")}, step={r.get("step")}')
    ws = r.get('ws', ws)
    step = r.get('step', '')
    time.sleep(2)
    
    # Submit email
    email = f'int{random.randint(10000,99999)}@havenhaus.in'
    r = api_call(pg, step, ws, [
        {'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP},
        {'input_type': 'UserRequestInput', 'identity': email}
    ], action_id='SIGNUP')
    print(f'Email: status={r.get("status")}, step={r.get("step")}')
    ws = r.get('ws', ws)
    
    # Get redirect URL
    full = r.get('full', {})
    redirect_url = full.get('redirect', {}).get('url', '')
    if redirect_url:
        ws_match = re.search(r'workflowStateHandle=([a-f0-9-]{36})', redirect_url)
        if ws_match:
            ws = ws_match.group(1)
    print(f'Redirect: {redirect_url[:100]}')
    time.sleep(3)
    
    # NOW: Navigate to the signup page
    if not redirect_url:
        redirect_url = f'{SIGNIN_BASE}/signup?workflowStateHandle={ws}'
    print(f'\nNavigating to signup page...')
    
    pg.goto(redirect_url, wait_until='load', timeout=60000)
    
    # Wait for the page to fully load
    print('Waiting for page to load...')
    time.sleep(10)
    
    # Check page state
    print(f'On page: {pg.url[:100]}')
    
    # Try to find form elements
    try:
        # Get page HTML structure
        html_info = pg.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
                type: i.type, name: i.name, id: i.id, placeholder: i.placeholder,
                autocomplete: i.autocomplete
            }));
            const buttons = Array.from(document.querySelectorAll('button')).map(b => ({
                text: b.textContent?.trim(), type: b.type
            }));
            const forms = document.querySelectorAll('form').length;
            return {inputs, buttons, forms};
        }""")
        print(f'\nForm info: {json.dumps(html_info, indent=2)}')
    except Exception as e:
        print(f'Error getting form info: {e}')
    
    # Try to make the API call from this page
    print('\nTrying API call from signup page...')
    signup_api = '/signup/api/execute'
    
    # Init on signup API
    fresh_ws = str(uuid.uuid4())
    r = api_call(pg, '', fresh_ws, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP}], api_path=signup_api)
    print(f'Signup Init: status={r.get("status")}')
    if r.get('status') == 200:
        signup_ws = r.get('ws', fresh_ws)
        signup_step = r.get('step', '')
        print(f'  step={signup_step}, ws={signup_ws}')
        
        time.sleep(2)
        
        # Name form
        r = api_call(pg, signup_step or 'start', signup_ws, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP}], api_path=signup_api)
        print(f'Name Form: status={r.get("status")}, step={r.get("step")}, actions={r.get("actions")}')
        if r.get('status') == 200:
            signup_ws = r.get('ws', signup_ws)
            signup_step = r.get('step', signup_step)
            
            time.sleep(2)
            
            # Name submit
            r = api_call(pg, signup_step, signup_ws, [
                {'input_type': 'FingerPrintRequestInput', 'fingerPrint': FP},
                {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': 'Test User'}
            ], action_id='SUBMIT', api_path=signup_api)
            print(f'Name Submit: status={r.get("status")}, step={r.get("step")}, actions={r.get("actions")}')
            if r.get('status') == 200:
                print('SUCCESS! Name submitted!')
                ws = r.get('ws', signup_ws)
            else:
                print(f'  Error: {json.dumps(r.get("full", {}))[:200]}')
    else:
        print(f'  Error: {json.dumps(r.get("full", {}))[:200]}')
    
    ctx.close()

print('\nDone!')
