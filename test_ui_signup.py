from playwright.sync_api import sync_playwright
import json, re, time, uuid, random
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
    ctx = p.chromium.launch_persistent_context('/tmp/ui-test-ctx', channel='chromium', headless=True,
        user_agent=UA, locale='en-US', timezone_id='America/New_York',
        proxy={'server': 'http://127.0.0.1:8899'}, args=['--no-sandbox'])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    # Navigate through OIDC flow
    page.goto(auth_url, wait_until='load', timeout=120000)
    try:
        page.wait_for_url('**signin.aws**workflowStateHandle**', timeout=90000)
    except:
        for i in range(30):
            time.sleep(1)
            if 'signin.aws' in page.url and 'workflowStateHandle' in page.url: break
    
    ws = re.search(r'workflowStateHandle=([a-f0-9-]{36})', page.url).group(1)
    print(f'WS: {ws}')
    print(f'URL: {page.url[:120]}')
    time.sleep(3)
    
    # Check what's on the login page
    print(f'\n=== Page content: {page.content()[:200]} ===')
    
    # Try to find and fill the email form
    email_input = page.query_selector('input[type="email"], input[id*="email"], input[name*="email"]')
    if email_input:
        print('Found email input')
        email_input.fill('testui@havenhaus.in')
        time.sleep(1)
        # Click the continue/signup button
        btn = page.query_selector('button[type="submit"], input[type="submit"], button:has-text("Continue"), button:has-text("Sign up")')
        if btn:
            print('Found submit button, clicking...')
            btn.click()
            time.sleep(5)
            print(f'After click URL: {page.url[:120]}')
            print(f'Page content: {page.content()[:500]}')
        else:
            print('No submit button found')
            # List all buttons
            buttons = page.query_selector_all('button, input[type="submit"], a[role="button"]')
            for b in buttons:
                print(f'  Button: {b.inner_text()[:30]} | {b.get_attribute("id")} | {b.get_attribute("class")[:30]}')
    else:
        print('No email input found')
        # List all inputs
        inputs = page.query_selector_all('input')
        for inp in inputs:
            t = inp.get_attribute('type')
            i = inp.get_attribute('id')
            print(f'  Input: type={t}, id={i}')
    
    time.sleep(3)
    
    # Check if we're on the signup page now
    if 'signup' in page.url:
        print(f'\n=== ON SIGNUP PAGE ===')
        print(f'URL: {page.url[:120]}')
        print(f'Content: {page.content()[:800]}')
        
        # Try to fill the name
        name_input = page.query_selector('input[type="text"], input:not([type="password"])')
        if name_input:
            print('Found name input, filling...')
            # Type character by character for realism
            name = 'Test User'
            for ch in name:
                name_input.type(ch, delay=random.uniform(50, 150))
            time.sleep(2)
            print('Name filled')
        
        # Find and click submit
        btn = page.query_selector('button[type="submit"], button:has-text("Continue"), button:has-text("Submit"), input[type="submit"]')
        if btn:
            print(f'Found button: {btn.inner_text()[:30]}')
            btn.click()
            time.sleep(5)
            print(f'After name submit URL: {page.url[:120]}')
            print(f'Content: {page.content()[:500]}')
        else:
            print('No submit button on signup page')
            buttons = page.query_selector_all('button, input[type="submit"]')
            for b in buttons:
                print(f'  Button: {b.inner_text()[:30]} | {b.get_attribute("id")}')
    
    ctx.close()
