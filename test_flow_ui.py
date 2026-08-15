from playwright.sync_api import sync_playwright
import json, re, time, random, uuid
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
    # Use a fresh profile with proxy
    ctx = p.chromium.launch_persistent_context('/tmp/flowui-ctx', channel='chromium', headless=True,
        user_agent=UA, locale='en-US', timezone_id='America/New_York',
        proxy={'server': 'http://127.0.0.1:8899'}, args=['--no-sandbox'])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    # Track network
    requests_made = []
    page.on("response", lambda r: requests_made.append(f"{r.status} {r.method} {r.url[:120]}"))
    
    # Navigate to auth URL
    page.goto(auth_url, wait_until='load', timeout=120000)
    
    # Wait for redirect to signin.aws
    try:
        page.wait_for_url('**signin.aws**workflowStateHandle**', timeout=90000)
    except:
        for i in range(30):
            time.sleep(1)
            if 'signin.aws' in page.url and 'workflowStateHandle' in page.url: break
    
    ws = re.search(r'workflowStateHandle=([a-f0-9-]{36})', page.url).group(1)
    print(f'WS: {ws}')
    time.sleep(random.uniform(5, 10))
    
    # Find email input and fill
    email_inputs = page.query_selector_all('input[type="email"], input')
    email_input = None
    for inp in email_inputs:
        t = inp.get_attribute('type')
        if t == 'email' or t is None:
            email_input = inp
            break
    
    if email_input:
        print('Found email input, typing...')
        email_input.click()
        time.sleep(random.uniform(1, 3))
        email = 'testflow@havenhaus.in'
        for ch in email:
            email_input.type(ch, delay=random.uniform(30, 100))
        time.sleep(random.uniform(2, 4))
        print(f'Email value: {email_input.input_value()}')
        
        # Click Continue
        btns = page.query_selector_all('button, input[type="submit"]')
        for btn in btns:
            txt = btn.inner_text()
            if 'continue' in txt.lower() or 'sign' in txt.lower() or 'submit' in txt.lower():
                print(f'Clicking: {txt}')
                btn.click()
                break
        else:
            if btns:
                print(f'Clicking first button: {btns[0].inner_text()}')
                btns[0].click()
        
        time.sleep(random.uniform(5, 10))
        print(f'After email submit URL: {page.url[:120]}')
        
        # Wait for the page to show name form
        time.sleep(5)
        body = page.evaluate("document.body ? document.body.innerText : ''")
        print(f'Body: {body[:200]}')
        
        # Check for name input
        if 'name' in body.lower() or 'enter your' in body.lower():
            print('\n=== NAME PAGE DETECTED ===')
            # Find text inputs
            text_inputs = page.query_selector_all('input[type="text"], input:not([type="password"]):not([type="email"])')
            name_input = None
            for inp in text_inputs:
                if inp.is_visible():
                    name_input = inp
                    break
            
            if name_input:
                print('Found name input, typing...')
                name_input.click()
                time.sleep(random.uniform(1, 3))
                name = 'Jack Joshi'
                for ch in name:
                    name_input.type(ch, delay=random.uniform(50, 150))
                time.sleep(random.uniform(2, 4))
                print(f'Name value: {name_input.input_value()}')
                
                # Click Continue
                btns = page.query_selector_all('button, input[type="submit"]')
                for btn in btns:
                    txt = btn.inner_text()
                    if 'continue' in txt.lower() or 'submit' in txt.lower():
                        print(f'Clicking: {txt}')
                        btn.click()
                        break
                else:
                    if btns:
                        btns[0].click()
                
                time.sleep(random.uniform(5, 10))
                print(f'After name submit URL: {page.url[:120]}')
                body = page.evaluate("document.body ? document.body.innerText : ''")
                print(f'Body: {body[:200]}')
            else:
                print('No name input found')
        else:
            print('Not on name page')
    
    # Print relevant network requests
    print(f'\n=== Network requests ({len(requests_made)}) ===')
    for r in requests_made:
        if 'api/execute' in r or 'ERR' in r:
            print(r)
    
    ctx.close()
