#!/usr/bin/env python3
"""
Capture the actual signup flow network requests.
We navigate through the signup page and capture all /api/execute calls.
"""
import sys, json, time, uuid, secrets, hashlib, base64
sys.path.insert(0, '/home/ubuntu/kiro-gen')
from playwright.sync_api import sync_playwright

SIGNIN_BASE = 'https://us-east-1.signin.aws/platform/d-9067642ac7'
CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
HTTP_PROXY_PORT = 8899

# Test email
email = 'test_capture_001@havenhaus.in'

# First, do the login flow to get to the signup redirect
def make_fp():
    return f"ECdITeCs:{base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')[:43]}"

requests_log = []

def capture_requests(context):
    def on_request(request):
        if '/api/execute' in request.url or 'signup' in request.url:
            requests_log.append({
                'url': request.url,
                'method': request.method,
                'post_data': request.post_data[:500] if request.post_data else None,
                'headers': dict(request.headers)
            })
            print(f"  [REQ] {request.method} {request.url}")
            if request.post_data:
                print(f"        Body: {request.post_data[:300]}")
    
    context.on('request', on_request)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        '/tmp/capture-profile',
        channel='chromium',
        headless=True,
        viewport={'width': 1920, 'height': 1080},
        user_agent=CHROME_UA,
        locale='en-US',
        timezone_id='America/New_York',
        proxy={'server': f'http://127.0.0.1:{HTTP_PROXY_PORT}'},
        args=['--no-sandbox', '--disable-dev-shm-usage'],
    )
    
    capture_requests(context)
    page = context.pages[0] if context.pages else context.new_page()
    
    # Step 1: Go to signin page to get workflow state
    print("=== Step 1: Navigate to signin ===")
    page.goto(f'{SIGNIN_BASE}/login', wait_until='load', timeout=30000)
    time.sleep(3)
    ws_match = __import__('re').search(r'workflowStateHandle=([a-f0-9-]{36})', page.url)
    ws = ws_match.group(1) if ws_match else str(uuid.uuid4())
    print(f"WS: {ws}")
    
    # Step 2: Init
    print("\n=== Step 2: Init ===")
    fp = make_fp()
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{SIGNIN_BASE}/api/execute', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    stepId: '',
                    workflowStateHandle: '{ws}',
                    inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: '{fp}'}}],
                    actionId: 'SUBMIT',
                    visitorId: crypto.randomUUID(),
                    requestId: crypto.randomUUID()
                }})
            }});
            return {{status: resp.status, data: await resp.json()}};
        }}
    """)
    print(f"Init: {json.dumps(result)[:300]}")
    ws = result['data'].get('workflowStateHandle', ws)
    current_step = result['data'].get('stepId', '')
    time.sleep(2)
    
    # Step 3: Load email form
    print("\n=== Step 3: Load email form ===")
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{SIGNIN_BASE}/api/execute', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    stepId: '{current_step}',
                    workflowStateHandle: '{ws}',
                    inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: '{fp}'}}],
                    actionId: 'SUBMIT',
                    visitorId: crypto.randomUUID(),
                    requestId: crypto.randomUUID()
                }})
            }});
            return {{status: resp.status, data: await resp.json()}};
        }}
    """)
    print(f"Load form: {json.dumps(result)[:300]}")
    ws = result['data'].get('workflowStateHandle', ws)
    current_step = result['data'].get('stepId', current_step)
    time.sleep(2)
    
    # Step 4: Submit email with SIGNUP
    print(f"\n=== Step 4: Submit email ({email}) ===")
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{SIGNIN_BASE}/api/execute', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    stepId: '{current_step}',
                    workflowStateHandle: '{ws}',
                    inputs: [
                        {{input_type: 'FingerPrintRequestInput', fingerPrint: '{fp}'}},
                        {{input_type: 'UserRequestInput', identity: '{email}'}}
                    ],
                    actionId: 'SIGNUP',
                    visitorId: crypto.randomUUID(),
                    requestId: crypto.randomUUID()
                }})
            }});
            return {{status: resp.status, data: await resp.json()}};
        }}
    """)
    print(f"Email: {json.dumps(result)[:500]}")
    data = result['data']
    ws = data.get('workflowStateHandle', ws)
    current_step = data.get('stepId', current_step)
    
    # Get the redirect URL
    redirect_url = ''
    if 'redirect' in data and isinstance(data['redirect'], dict):
        redirect_url = data['redirect'].get('url', '')
    print(f"Redirect: {redirect_url}")
    time.sleep(2)
    
    # Step 5: Now make signup API calls (staying on login page)
    print("\n=== Step 5: Signup API calls ===")
    
    # 5a: Init on signup
    print("  [5a] Signup init...")
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    stepId: '',
                    workflowStateHandle: '{ws}',
                    inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: '{fp}'}}],
                    actionId: 'SUBMIT',
                    visitorId: crypto.randomUUID(),
                    requestId: crypto.randomUUID()
                }})
            }});
            return {{status: resp.status, data: await resp.json()}};
        }}
    """)
    print(f"  Signup init: {json.dumps(result)[:300]}")
    signup_ws = result['data'].get('workflowStateHandle', ws)
    signup_step = result['data'].get('stepId', '')
    time.sleep(2)
    
    # 5b: Load name form
    print("  [5b] Load name form...")
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    stepId: '{signup_step}',
                    workflowStateHandle: '{signup_ws}',
                    inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: '{fp}'}}],
                    actionId: 'SUBMIT',
                    visitorId: crypto.randomUUID(),
                    requestId: crypto.randomUUID()
                }})
            }});
            return {{status: resp.status, data: await resp.json()}};
        }}
    """)
    print(f"  Name form: {json.dumps(result)[:500]}")
    signup_ws = result['data'].get('workflowStateHandle', signup_ws)
    signup_step = result['data'].get('stepId', signup_step)
    print(f"  Signup step: {signup_step}")
    print(f"  Actions: {result['data'].get('actionIdList', [])}")
    time.sleep(2)
    
    # 5c: Submit name - try with empty actionId first
    print("  [5c] Submit name (actionId='SUBMIT')...")
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    stepId: '{signup_step}',
                    workflowStateHandle: '{signup_ws}',
                    inputs: [
                        {{input_type: 'FingerPrintRequestInput', fingerPrint: '{fp}'}},
                        {{input_type: 'TextInput', key: 'verifiedUserName', value: 'Test User'}}
                    ],
                    actionId: 'SUBMIT',
                    visitorId: crypto.randomUUID(),
                    requestId: crypto.randomUUID()
                }})
            }});
            return {{status: resp.status, data: await resp.json()}};
        }}
    """)
    print(f"  Name SUBMIT: {json.dumps(result)[:500]}")
    
    # Try with empty actionId
    print("  [5d] Submit name (empty actionId)...")
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    stepId: '{signup_step}',
                    workflowStateHandle: '{signup_ws}',
                    inputs: [
                        {{input_type: 'FingerPrintRequestInput', fingerPrint: '{fp}'}},
                        {{input_type: 'TextInput', key: 'verifiedUserName', value: 'Test User'}}
                    ],
                    actionId: '',
                    visitorId: crypto.randomUUID(),
                    requestId: crypto.randomUUID()
                }})
            }});
            return {{status: resp.status, data: await resp.json()}};
        }}
    """)
    print(f"  Name empty actionId: {json.dumps(result)[:500]}")
    
    # Try with different input key
    print("  [5e] Submit name (key='name')...")
    result = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                method: 'POST',
                credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    stepId: '{signup_step}',
                    workflowStateHandle: '{signup_ws}',
                    inputs: [
                        {{input_type: 'FingerPrintRequestInput', fingerPrint: '{fp}'}},
                        {{input_type: 'TextInput', key: 'name', value: 'Test User'}}
                    ],
                    actionId: 'SUBMIT',
                    visitorId: crypto.randomUUID(),
                    requestId: crypto.randomUUID()
                }})
            }});
            return {{status: resp.status, data: await resp.json()}};
        }}
    """)
    print(f"  Name key='name': {json.dumps(result)[:500]}")
    
    context.close()

# Save all captured requests
with open('/home/ubuntu/kiro-gen/captured_requests.json', 'w') as f:
    json.dump(requests_log, f, indent=2)
print(f"\nCaptured {len(requests_log)} requests")
