from playwright.sync_api import sync_playwright
import json, re, time, uuid
from urllib.parse import quote
import secrets, hashlib, base64
from curl_cffi import requests as cffi

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
CALLBACK_PORT = 9997

reg = cffi.post('https://oidc.us-east-1.amazonaws.com/client/register', proxy='http://127.0.0.1:8899',
                json={'clientName': 't', 'clientType': 'public', 'scopes': ['codewhisperer:completions'],
                      'grantTypes': ['authorization_code'], 'redirectUris': [f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'],
                      'issuerUrl': 'https://view.awsapps.com/start'})
client_id = reg.json()['clientId']
cv = secrets.token_urlsafe(64)[:128]
cc = base64.urlsafe_b64encode(hashlib.sha256(cv.encode()).digest()).rstrip(b'=').decode()
auth_url = f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code&client_id={client_id}&redirect_uri={quote(f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback")}&scopes=codewhisperer%3Acompletions&state=t&code_challenge={cc}&code_challenge_method=S256'

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context('/tmp/test8-ctx', channel='chromium', headless=True,
        user_agent=UA, locale='en-US', timezone_id='America/New_York',
        proxy={'server': 'http://127.0.0.1:8899'}, args=['--no-sandbox'])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(auth_url, wait_until='load', timeout=120000)
    try:
        page.wait_for_url('**signin.aws**workflowStateHandle**', timeout=90000)
    except:
        for i in range(30):
            time.sleep(1)
            if 'signin.aws' in page.url and 'workflowStateHandle' in page.url: break
    ws = re.search(r'workflowStateHandle=([a-f0-9-]{36})', page.url).group(1)
    print(f'WS: {ws}')
    time.sleep(3)
    
    API_URL = 'https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute'
    SIGNUP_API = 'https://us-east-1.signin.aws/platform/d-9067642ac7/signup/api/execute'
    
    def eval_fetch(base, step, ws, inputs, action):
        return page.evaluate(f"""async () => {{
            const resp = await fetch('{base}', {{method: 'POST', credentials: 'include',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{stepId: '{step}', workflowStateHandle: '{ws}', actionId: '{action}', inputs: {json.dumps(inputs)},
                visitorId: '{str(uuid.uuid4())}', requestId: '{str(uuid.uuid4())}'}})}});
            return {{status: resp.status, data: await resp.json()}};}}""")
    
    # Login steps via eval_fetch
    r = eval_fetch(API_URL, '', ws, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': 'fp'}], '')
    print(f'Init: {r["status"]}')
    ws = r['data'].get('workflowStateHandle', ws)
    step = r['data'].get('stepId', '')
    time.sleep(2)
    
    r = eval_fetch(API_URL, step, ws, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': 'fp'}], '')
    print(f'EmailForm: {r["status"]}')
    ws = r['data'].get('workflowStateHandle', ws)
    step = r['data'].get('stepId', step)
    time.sleep(2)
    
    r = eval_fetch(API_URL, step, ws, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': 'fp'},
                                        {'input_type': 'UserRequestInput', 'identity': 'testeval@havenhaus.in'}], 'SIGNUP')
    print(f'EmailSubmit: {r["status"]}')
    ws = r['data'].get('workflowStateHandle', ws)
    step = r['data'].get('stepId', step)
    redirect = r['data'].get('redirect', {}).get('url', '')
    ws_from_redirect = re.search(r'workflowStateHandle=([a-f0-9-]{36})', redirect)
    ws_r = ws_from_redirect.group(1) if ws_from_redirect else ws
    print(f'  step={step}, ws_r={ws_r[:20]}...')
    print(f'  Redirect: {redirect[:100]}')
    time.sleep(3)
    
    # Navigate to signup page
    page.goto(redirect, wait_until='load', timeout=60000)
    print(f'On: {page.url[:100]}')
    time.sleep(5)
    
    # Attempt 1: eval_fetch on signup API with ws from redirect
    r = eval_fetch(SIGNUP_API, 'user-signup', ws_r, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': 'fp'},
                                                      {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': 'Test User'}], 'SUBMIT')
    print(f'NameSubmit(eval, signup API): {r["status"]} - {json.dumps(r["data"])[:100]}')
    
    # Attempt 2: page.request.post on signup API
    if r['status'] != 200:
        r = page.request.post(SIGNUP_API, data=json.dumps({
            'stepId': 'user-signup', 'workflowStateHandle': ws_r, 'actionId': 'SUBMIT',
            'inputs': [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': 'fp'},
                       {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': 'Test User'}],
            'visitorId': str(uuid.uuid4()), 'requestId': str(uuid.uuid4())}),
            headers={'Content-Type': 'application/json'})
        print(f'NameSubmit(request.post, signup API): {r.status}')
    
    # Attempt 3: eval_fetch on login API from signup page
    if r.status if hasattr(r, 'status') else r['status'] != 200:
        r = eval_fetch(API_URL, 'user-signup', ws_r, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': 'fp'},
                                                       {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': 'Test User'}], 'SUBMIT')
        print(f'NameSubmit(eval, login API from signup page): {r["status"]} - {json.dumps(r["data"])[:100]}')
    
    # Attempt 4: Navigate back to login page, then name submit
    if r.status if hasattr(r, 'status') else r['status'] != 200:
        login_url = f'https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle={ws_r}'
        page.goto(login_url, wait_until='load', timeout=30000)
        print(f'On: {page.url[:100]}')
        time.sleep(3)
        r = eval_fetch(API_URL, 'user-signup', ws_r, [{'input_type': 'FingerPrintRequestInput', 'fingerPrint': 'fp'},
                                                       {'input_type': 'TextInput', 'key': 'verifiedUserName', 'value': 'Test User'}], 'SUBMIT')
        print(f'NameSubmit(eval, login page): {r["status"]} - {json.dumps(r["data"])[:100]}')
    
    ctx.close()
