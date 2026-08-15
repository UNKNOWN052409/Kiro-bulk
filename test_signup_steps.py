#!/usr/bin/env python3
"""Test what happens when we use the login API with user-signup step after email submit."""
import time
import json
import random
import uuid
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

SIGNIN_BASE = 'https://us-east-1.signin.aws/platform/d-9067642ac7'
CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
FINGERPRINT = {"browser": "Chrome", "version": "124.0.0.0", "os": "Windows"}

def api_call(page, base, step_id, ws, inputs, action_id='', extra_path=''):
    url = f'{base}{extra_path}/api/execute'
    payload = {
        'workflowStateHandle': ws,
        'stepId': step_id,
        'actionId': action_id,
        'inputs': inputs
    }
    js = f"""
    (async () => {{
        const resp = await fetch('{url}', {{
            method: 'POST',
            credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({json.dumps(payload)})
        }});
        let data = {{}};
        try {{ data = await resp.json(); }} catch(e) {{}}
        return JSON.stringify({{status: resp.status, data: data}});
    }})()
    """
    return page.evaluate(js)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        '/tmp/test-steps-profile',
        channel='chromium',
        headless=True,
        viewport={'width': 1920, 'height': 1080},
        user_agent=CHROME_UA,
        locale='en-US',
        proxy={'server': 'http://127.0.0.1:8899'},
        args=['--no-sandbox', '--disable-dev-shm-usage'],
    )
    page = context.pages[0] if context.pages else context.new_page()
    
    # Navigate to login page to get initial WS
    print("[0] Navigate to login...")
    page.goto(f'{SIGNIN_BASE}/login', wait_until='load', timeout=30000)
    # Wait for JS redirect
    time.sleep(3)
    print(f"    URL: {page.url}")
    
    parsed = urlparse(page.url)
    qs = parse_qs(parsed.query)
    ws = qs.get('workflowStateHandle', [''])[0]
    print(f"    WS: {ws}")
    
    if not ws:
        print("    No WS! Page didn't redirect properly.")
        context.close()
        exit(1)
    
    # Init
    print("\n[1] Init...")
    result = json.loads(api_call(page, SIGNIN_BASE, '', ws, 
        [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FINGERPRINT}]))
    print(f"    Status: {result['status']}")
    if result['status'] == 200:
        ws = result['data'].get('workflowStateHandle', ws)
        step = result['data'].get('stepId', '')
        print(f"    step={step}, ws={ws[:20]}...")
    
    time.sleep(1)
    
    # Load email form
    print("\n[2] Load email form (step=start)...")
    result = json.loads(api_call(page, SIGNIN_BASE, 'start', ws,
        [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FINGERPRINT}]))
    print(f"    Status: {result['status']}")
    if result['status'] == 200:
        ws = result['data'].get('workflowStateHandle', ws)
        step = result['data'].get('stepId', '')
        actions = result['data'].get('actionIdList', [])
        print(f"    step={step}, actions={actions}")
    
    time.sleep(1)
    
    # Submit email
    email = f'test{random.randint(100000,999999)}@havenhaus.in'
    print(f"\n[3] Submit email: {email}")
    result = json.loads(api_call(page, SIGNIN_BASE, step, ws,
        [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FINGERPRINT},
         {'input_type': 'UserRequestInput', 'identity': email}],
        action_id='SIGNUP'))
    print(f"    Status: {result['status']}")
    if result['status'] == 200:
        ws = result['data'].get('workflowStateHandle', ws)
        step = result['data'].get('stepId', '')
        print(f"    step={step}, ws={ws[:20]}...")
        # Check for redirect URL
        msg = result['data'].get('message', {})
        redirect = msg.get('continueUrl', '') or result['data'].get('continueUrl', '')
        print(f"    redirect={redirect[:100]}")
    
    time.sleep(1)
    
    # NOW THE KEY TEST: use the SAME login API endpoint but with different stepIds
    print(f"\n[4] Test different stepIds on LOGIN API after email submit...")
    
    # Test 1: stepId='user-signup' with SUBMIT action and name input
    print("    Test 1: stepId='user-signup', action='SUBMIT', name input")
    result = json.loads(api_call(page, SIGNIN_BASE, 'user-signup', ws,
        [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FINGERPRINT},
         {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': 'Test User'}],
        action_id='SUBMIT'))
    print(f"    Status: {result['status']}")
    if result['status'] == 200:
        ws = result['data'].get('workflowStateHandle', ws)
        step = result['data'].get('stepId', '')
        print(f"    SUCCESS! step={step}")
    else:
        print(f"    Failed: {json.dumps(result['data']).get('message', {}).get('text', '')[:100]}")
    
    time.sleep(1)
    
    # Test 2: stepId='user-signup' with empty action and name input
    print("\n    Test 2: stepId='user-signup', action='', name input")
    result = json.loads(api_call(page, SIGNIN_BASE, 'user-signup', ws,
        [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FINGERPRINT},
         {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': 'Test User'}],
        action_id=''))
    print(f"    Status: {result['status']}")
    if result['status'] == 200:
        ws = result['data'].get('workflowStateHandle', ws)
        step = result['data'].get('stepId', '')
        print(f"    SUCCESS! step={step}")
    else:
        print(f"    Failed: {json.dumps(result['data']).get('message', {}).get('text', '')[:100]}")
    
    time.sleep(1)
    
    # Test 3: stepId='user-signup' with SIGNUP action
    print("\n    Test 3: stepId='user-signup', action='SIGNUP'")
    result = json.loads(api_call(page, SIGNIN_BASE, 'user-signup', ws,
        [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FINGERPRINT},
         {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': 'Test User'}],
        action_id='SIGNUP'))
    print(f"    Status: {result['status']}")
    if result['status'] == 200:
        ws = result['data'].get('workflowStateHandle', ws)
        step = result['data'].get('stepId', '')
        print(f"    SUCCESS! step={step}")
    else:
        print(f"    Failed: {json.dumps(result['data']).get('message', {}).get('text', '')[:100]}")
    
    time.sleep(1)
    
    # Test 4: Use the updated WS from test 2/3 and try the signup API path
    print("\n[5] Test signup API path with updated WS...")
    
    # 4a: init on signup API
    print("    4a: Signup API init (stepId='')")
    result = json.loads(api_call(page, SIGNIN_BASE, '', ws,
        [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FINGERPRINT}],
        extra_path='/signup'))
    print(f"    Status: {result['status']}")
    if result['status'] == 200:
        ws2 = result['data'].get('workflowStateHandle', ws)
        step2 = result['data'].get('stepId', '')
        print(f"    step={step2}, ws={ws2[:20]}...")
        
        time.sleep(1)
        
        # 4b: get name form on signup API
        print("    4b: Signup API load name form (step=start)")
        result = json.loads(api_call(page, SIGNIN_BASE, 'start', ws2,
            [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FINGERPRINT}],
            extra_path='/signup'))
        print(f"    Status: {result['status']}")
        if result['status'] == 200:
            ws2 = result['data'].get('workflowStateHandle', ws2)
            step2 = result['data'].get('stepId', '')
            actions = result['data'].get('actionIdList', [])
            print(f"    step={step2}, actions={actions}")
            
            time.sleep(1)
            
            # 4c: submit name on signup API
            print(f"    4c: Signup API submit name (step={step2})")
            result = json.loads(api_call(page, SIGNIN_BASE, step2, ws2,
                [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': FINGERPRINT},
                 {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': 'Test User'}],
                action_id='SUBMIT',
                extra_path='/signup'))
            print(f"    Status: {result['status']}")
            if result['status'] == 200:
                ws2 = result['data'].get('workflowStateHandle', ws2)
                step2 = result['data'].get('stepId', '')
                print(f"    SUCCESS! step={step2}")
            else:
                print(f"    Failed: {json.dumps(result['data']).get('message', {}).get('text', '')[:100]}")
    else:
        print(f"    Failed: {json.dumps(result['data']).get('message', {}).get('text', '')[:100]}")
    
    context.close()

print("\nDone!")
