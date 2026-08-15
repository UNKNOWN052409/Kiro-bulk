from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
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
    browser = p.chromium.launch(channel='chromium', headless=True, args=['--no-sandbox'])
    ctx = browser.new_context(
        user_agent=UA,
        locale='en-US',
        timezone_id='America/New_York',
        proxy={'server': 'http://127.0.0.1:8899'}
    )
    stealth = Stealth()
    stealth.apply_stealth_sync(ctx)
    page = ctx.new_page()
    
    # Track responses
    responses = []
    page.on("response", lambda r: responses.append(f"{r.status} {r.url[:100]}") if 'api/execute' in r.url else None)
    
    page.goto(auth_url, wait_until='load', timeout=120000)
    try:
        page.wait_for_url('**signin.aws**workflowStateHandle**', timeout=90000)
    except:
        for i in range(30):
            time.sleep(1)
            if 'signin.aws' in page.url and 'workflowStateHandle' in page.url: break
    
    ws = re.search(r'workflowStateHandle=([a-f0-9-]{36})', page.url).group(1)
    print(f'WS: {ws}')
    
    # Wait for full page render
    for i in range(30):
        time.sleep(2)
        try:
            body = page.evaluate("document.body ? document.body.innerText : ''")
            if len(body) > 50:
                break
        except:
            pass
    
    # Dismiss cookie banner
    for btn_text in ["Decline", "Accept", "Dismiss"]:
        try:
            btns = page.get_by_role("button", name=btn_text, exact=True).all()
            for btn in btns:
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    print(f"Dismissed cookie: {btn_text}")
                    time.sleep(2)
                    break
        except:
            pass
    
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f'Body: {body[:200]}')
    
    # Find email input
    email_inputs = page.locator('input[type="email"], input').all()
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
        email = 'testst2@havenhaus.in'
        email_input.type(email, delay=random.uniform(50, 120))
        time.sleep(random.uniform(2, 4))
        print(f'Email value: {email_input.input_value()}')
        
        # Click Continue
        btns = page.locator('button, input[type="submit"]').all()
        for btn in btns:
            txt = btn.inner_text()
            if 'continue' in txt.lower() or 'sign' in txt.lower():
                print(f'Clicking: {txt}')
                btn.click()
                break
        else:
            if btns:
                btns[0].click()
        
        # Wait for page to update
        time.sleep(random.uniform(8, 15))
        print(f'After email submit URL: {page.url[:120]}')
        
        # Wait for render
        for i in range(30):
            time.sleep(2)
            try:
                body = page.evaluate("document.body ? document.body.innerText : ''")
                if len(body) > 50:
                    break
            except:
                pass
        
        body = page.evaluate("document.body ? document.body.innerText : ''")
        print(f'Body after email: {body[:300]}')
        
        # Check for name page
        if 'enter your name' in body.lower() or 'name' in body.lower():
            print('\n=== NAME PAGE DETECTED ===')
            
            # Find name input
            text_inputs = page.locator('input[type="text"]').all()
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
                name_input.type(name, delay=random.uniform(50, 150))
                time.sleep(random.uniform(2, 4))
                print(f'Name value: {name_input.input_value()}')
                
                btns = page.locator('button, input[type="submit"]').all()
                for btn in btns:
                    txt = btn.inner_text()
                    if 'continue' in txt.lower():
                        print(f'Clicking: {txt}')
                        btn.click()
                        break
                else:
                    if btns:
                        btns[0].click()
                
                time.sleep(random.uniform(8, 15))
                body = page.evaluate("document.body ? document.body.innerText : ''")
                print(f'After name submit body: {body[:300]}')
                
                if 'ERR-837' in body:
                    print('\n[FAIL] ERR-837 detected')
                elif 'password' in body.lower() or 'enter password' in body.lower():
                    print('\n[SUCCESS] Password page reached!')
                else:
                    print(f'\n[UNKNOWN] Current state: {body[:100]}')
            else:
                print('No name input found')
                all_inputs = page.locator('input').all()
                for inp in all_inputs:
                    print(f'  Input: type={inp.get_attribute("type")}, id={inp.get_attribute("id")}')
        else:
            print('\nNot on name page')
    
    # Print API responses
    print(f'\n=== API responses ({len(responses)}) ===')
    for r in responses:
        print(r)
    
    ctx.close()
    browser.close()
