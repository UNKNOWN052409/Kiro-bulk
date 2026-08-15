#!/usr/bin/env python3
"""Capture actual network requests from the AWS signup page."""
import time
from playwright.sync_api import sync_playwright

SIGNIN_BASE = 'https://us-east-1.signin.aws/platform/d-9067642ac7'
CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

requests_log = []

def on_request(request):
    url = request.url
    if 'api.execute' in url or 'execute' in url or 'platform' in url:
        requests_log.append({
            'url': url,
            'method': request.method,
            'headers': dict(request.headers),
        })

def on_response(response):
    url = response.url
    if 'api.execute' in url or 'execute' in url or 'platform' in url:
        try:
            body = response.text()
            print(f"  [{response.status}] {url[:120]}")
            print(f"    Response: {body[:500]}")
        except:
            pass

# First, do the login flow to get the signup redirect URL
with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        '/tmp/capture-profile',
        channel='chromium',
        headless=True,
        viewport={'width': 1920, 'height': 1080},
        user_agent=CHROME_UA,
        locale='en-US',
        proxy={'server': 'http://127.0.0.1:8899'},
        args=['--no-sandbox', '--disable-dev-shm-usage'],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.on('request', on_request)
    page.on('response', on_response)
    
    # Navigate to login page
    print("[1] Navigate to login...")
    page.goto(f'{SIGNIN_BASE}/login', wait_until='load', timeout=30000)
    print(f"    URL: {page.url}")
    time.sleep(3)
    
    # Get workflow state from URL
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(page.url)
    qs = parse_qs(parsed.query)
    ws = qs.get('workflowStateHandle', [''])[0]
    print(f"    WS: {ws}")
    
    # Init
    print("[2] Init...")
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
                inputs: [{{
                    input_type: 'FingerPrintRequestInput',
                    fingerPrint: {repr(fingerprint)}
                }}]
            }})
        }});
        const data = await resp.json();
        return JSON.stringify({{status: resp.status, step: data.stepId, ws: data.workflowStateHandle, actions: data.actionIdList}});
    }})()
    """
    result = page.evaluate(js_code)
    print(f"    Init result: {result}")
    time.sleep(2)
    
    # Submit email
    import random
    email = f'test{random.randint(1000,9999)}@havenhaus.in'
    print(f"[3] Submit email: {email}")
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
                inputs: [{{
                    input_type: 'FingerPrintRequestInput',
                    fingerPrint: {repr(fingerprint)}
                }}, {{
                    input_type: 'UserRequestInput',
                    identity: '{email}'
                }}]
            }})
        }});
        const data = await resp.json();
        return JSON.stringify({{status: resp.status, step: data.stepId, ws: data.workflowStateHandle, 
                             redirectUrl: data.continueUrl || data.message?.continueUrl || ''}});
    }})()
    """
    result = page.evaluate(js_code)
    print(f"    Email result: {result}")
    
    # Parse the redirect URL
    import json
    email_result = json.loads(result)
    redirect_url = email_result.get('redirectUrl', '')
    if redirect_url:
        print(f"\n[4] Redirect URL: {redirect_url}")
        signup_ws = redirect_url.split('workflowStateHandle=')[1] if 'workflowStateHandle=' in redirect_url else ''
        print(f"    Signup WS: {signup_ws}")
        
        # Navigate to signup page
        print(f"\n[5] Navigate to signup page...")
        page.goto(redirect_url, wait_until='load', timeout=30000)
        print(f"    On page: {page.url}")
        time.sleep(5)
        
        # Now let's see what API calls the page makes
        # Try to make a fetch from the signup page
        print(f"\n[6] Try fetch from signup page to signup API...")
        js_code = f"""
        (async () => {{
            // Try different endpoints
            const results = [];
            // 1. Try /api/execute on current origin
            try {{
                const resp1 = await fetch('/api/execute', {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{workflowStateHandle: '{signup_ws}', stepId: '', actionId: '', inputs: []}})
                }});
                results.push({{endpoint: '/api/execute', status: resp1.status}});
            }} catch(e) {{ results.push({{endpoint: '/api/execute', error: e.message}}); }}
            
            // 2. Try /signup/api/execute
            try {{
                const resp2 = await fetch('/signup/api/execute', {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{workflowStateHandle: '{signup_ws}', stepId: '', actionId: '', inputs: []}})
                }});
                const data2 = await resp2.json();
                results.push({{endpoint: '/signup/api/execute', status: resp2.status, data: JSON.stringify(data2).slice(0, 200)}});
            }} catch(e) {{ results.push({{endpoint: '/signup/api/execute', error: e.message}}); }}
            
            // 3. Try with signup WS and stepId=''
            try {{
                const resp3 = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
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
                const data3 = await resp3.json();
                results.push({{endpoint: '{SIGNIN_BASE}/signup/api/execute', status: resp3.status, step: data3.stepId, ws: data3.workflowStateHandle, actions: data3.actionIdList}});
            }} catch(e) {{ results.push({{endpoint: '{SIGNIN_BASE}/signup/api/execute', error: e.message}}); }}
            
            // 4. Try with signup WS and stepId='user-signup'
            try {{
                const resp4 = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        workflowStateHandle: '{signup_ws}',
                        stepId: 'user-signup',
                        actionId: 'SUBMIT',
                        inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}}]
                    }})
                }});
                const data4 = await resp4.json();
                results.push({{endpoint: 'signup ws=user-signup', status: resp4.status, step: data4.stepId, ws: data4.workflowStateHandle, actions: data4.actionIdList, msg: (data4.message?.text||'').slice(0,100)}});
            }} catch(e) {{ results.push({{endpoint: 'signup ws=user-signup', error: e.message}}); }}
            
            return JSON.stringify(results);
        }})()
        """
        result = page.evaluate(js_code)
        print(f"    Results: {result}")
        
        time.sleep(3)
        
        # 5. Try fresh init on signup API with a NEW ws (not from email redirect)
        print(f"\n[7] Fresh init on signup API with new WS...")
        import uuid
        new_ws = str(uuid.uuid4())
        js_code = f"""
        (async () => {{
            const results = [];
            // Fresh init
            try {{
                const resp = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                    method: 'POST',
                    credentials: 'include',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        workflowStateHandle: '{new_ws}',
                        stepId: '',
                        actionId: '',
                        inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}}]
                    }})
                }});
                const data = await resp.json();
                results.push({{step: 'init', status: resp.status, newWs: data.workflowStateHandle, stepId: data.stepId, actions: data.actionIdList}});
                
                if (data.workflowStateHandle) {{
                    // Use the new ws to get the next step
                    const resp2 = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            workflowStateHandle: data.workflowStateHandle,
                            stepId: 'start',
                            actionId: '',
                            inputs: [{{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}}]
                        }})
                    }});
                    const data2 = await resp2.json();
                    results.push({{step: 'after_init', status: resp2.status, stepId: data2.stepId, actions: data2.actionIdList, msg: (data2.message?.text||'').slice(0,100)}});
                    
                    if (data2.stepId && data2.actionIdList) {{
                        // Try to submit with the actions listed
                        for (const action of data2.actionIdList) {{
                            const resp3 = await fetch('{SIGNIN_BASE}/signup/api/execute', {{
                                method: 'POST',
                                credentials: 'include',
                                headers: {{'Content-Type': 'application/json'}},
                                body: JSON.stringify({{
                                    workflowStateHandle: data2.workflowStateHandle,
                                    stepId: data2.stepId,
                                    actionId: action,
                                    inputs: [
                                        {{input_type: 'FingerPrintRequestInput', fingerPrint: {repr(fingerprint)}}},
                                        {{input_type: 'TextInput', key: 'verifiedUserName', value: 'Test User'}}
                                    ]
                                }})
                            }});
                            const data3 = await resp3.json();
                            results.push({{step: `submit_${action}`, status: resp3.status, stepId: data3.stepId, msg: (data3.message?.text||'').slice(0,100)}});
                        }}
                    }}
                }}
            }} catch(e) {{ results.push({{error: e.message}}); }}
            
            return JSON.stringify(results);
        }})()
        """
        result = page.evaluate(js_code)
        print(f"    Fresh init results: {result}")
    
    time.sleep(2)
    context.close()

print("\nDone!")
