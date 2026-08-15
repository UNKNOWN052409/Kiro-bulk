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
    ctx = p.chromium.launch_persistent_context('/tmp/ui2-ctx', channel='chromium', headless=True,
        user_agent=UA, locale='en-US', timezone_id='America/New_York',
        proxy={'server': 'http://127.0.0.1:8899'}, args=['--no-sandbox'])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    # Track all network requests
    requests_made = []
    page.on("request", lambda r: requests_made.append(f"{r.method} {r.url[:150]}"))
    page.on("response", lambda r: requests_made.append(f"  -> {r.status} {r.url[:150]}"))
    
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
    
    # Find the email input and type into it
    print('\nLooking for inputs...')
    inputs = page.query_selector_all('input')
    for inp in inputs:
        print(f'  Input: type={inp.get_attribute("type")}, id={inp.get_attribute("id")}, name={inp.get_attribute("name")}')
    
    # Find the email input
    email_input = page.query_selector('input[type="email"]')
    if not email_input:
        email_input = page.query_selector('input')
    
    if email_input:
        print('\nTyping email...')
        email_input.click()
        time.sleep(0.5)
        email_input.type('testui2@havenhaus.in', delay=random.uniform(50, 150))
        time.sleep(2)
        print(f'Input value: {email_input.input_value()}')
        
        # Find all buttons
        print('\nLooking for buttons...')
        buttons = page.query_selector_all('button, input[type="submit"], div[role="button"]')
        for b in buttons:
            txt = b.inner_text()[:40] if b.inner_text() else '(no text)'
            bid = b.get_attribute('id')
            bclass = b.get_attribute('class')[:50] if b.get_attribute('class') else ''
            print(f'  Button: "{txt}" id={bid} class={bclass}')
        
        # Click the first button (likely "Continue" or "Sign in")
        if buttons:
            btn = buttons[0]
            print(f'\nClicking button: {btn.inner_text()[:30]}')
            btn.click()
            time.sleep(5)
            print(f'After click URL: {page.url[:150]}')
            
            # Wait and check again
            time.sleep(5)
            print(f'URL after 5s: {page.url[:150]}')
            
            # Check for signup page
            if 'signup' in page.url:
                print('\n=== ON SIGNUP PAGE ===')
                print(f'Content: {page.content()[:1000]}')
                
                # Find name input
                name_inputs = page.query_selector_all('input')
                for ni in name_inputs:
                    print(f'  Input: type={ni.get_attribute("type")}, id={ni.get_attribute("id")}')
                
                # Type name
                name_input = page.query_selector('input[type="text"]')
                if not name_input:
                    name_input = page.query_selector('input:not([type="password"])')
                if name_input:
                    print('\nTyping name...')
                    for ch in 'Test User':
                        name_input.type(ch, delay=random.uniform(50, 150))
                    time.sleep(2)
                    print(f'Name value: {name_input.input_value()}')
                    
                    # Click submit
                    buttons = page.query_selector_all('button, input[type="submit"]')
                    if buttons:
                        buttons[0].click()
                        time.sleep(5)
                        print(f'After name submit URL: {page.url[:150]}')
                        print(f'Content: {page.content()[:500]}')
            else:
                print(f'\nNot on signup page. Content: {page.content()[:500]}')
    
    # Print network requests
    print(f'\n=== Network requests ({len(requests_made)}) ===')
    for r in requests_made[:50]:
        print(r)
    
    ctx.close()
