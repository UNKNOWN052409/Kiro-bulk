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
    
    page.goto(auth_url, wait_until='load', timeout=120000)
    try:
        page.wait_for_url('**signin.aws**workflowStateHandle**', timeout=90000)
    except:
        for i in range(30):
            time.sleep(1)
            if 'signin.aws' in page.url and 'workflowStateHandle' in page.url: break
    
    ws = re.search(r'workflowStateHandle=([a-f0-9-]{36})', page.url).group(1)
    print(f'WS: {ws}')
    
    # Wait for full render
    for i in range(40):
        time.sleep(2)
        try:
            body = page.evaluate("document.body ? document.body.innerText : ''")
            if len(body) > 50:
                break
        except:
            pass
    
    # Dismiss cookie
    for btn_text in ["Decline", "Accept", "Dismiss"]:
        try:
            btns = page.get_by_role("button", name=btn_text, exact=True).all()
            for btn in btns:
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    print(f"Dismissed: {btn_text}")
                    time.sleep(2)
                    break
        except:
            pass
    
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f'Initial body: {body[:200]}')
    
    # Find email input and fill
    email_inputs = page.locator('input[type="email"], input').all()
    email_input = None
    for inp in email_inputs:
        t = inp.get_attribute('type')
        if t == 'email' or t is None:
            email_input = inp
            break
    
    if email_input:
        print('Typing email...')
        email_input.click()
        time.sleep(random.uniform(1, 3))
        email = 'testst3@havenhaus.in'
        email_input.type(email, delay=random.uniform(50, 120))
        time.sleep(random.uniform(2, 4))
        
        btns = page.locator('button, input[type="submit"]').all()
        for btn in btns:
            txt = btn.inner_text()
            if 'continue' in txt.lower() or 'sign' in txt.lower():
                btn.click()
                print(f'Clicked: {txt}')
                break
        else:
            if btns:
                btns[0].click()
        
        # Wait LONGER for the signup page to load
        print('Waiting for signup page...')
        time.sleep(30)
        
        # Keep checking
        for i in range(30):
            time.sleep(3)
            url = page.url
            body = page.evaluate("document.body ? document.body.innerText : ''")
            print(f'  [{i}] URL: {url[:80]} | Body: {body[:80]}')
            if 'signup' in url or 'name' in body.lower() or 'password' in body.lower():
                break
        
        body = page.evaluate("document.body ? document.body.innerText : ''")
        print(f'\nFinal body: {body[:300]}')
        
        # Check for name input on signup page
        text_inputs = page.locator('input[type="text"]').all()
        for inp in text_inputs:
            if inp.is_visible():
                print(f'\nFound visible text input!')
                inp.click()
                time.sleep(1)
                name = 'Jack Joshi'
                inp.type(name, delay=random.uniform(50, 150))
                time.sleep(2)
                print(f'Name: {inp.input_value()}')
                
                # Click Continue
                btns = page.locator('button, input[type="submit"]').all()
                for btn in btns:
                    txt = btn.inner_text()
                    if 'continue' in txt.lower():
                        btn.click()
                        print(f'Clicked: {txt}')
                        break
                else:
                    if btns:
                        btns[0].click()
                
                time.sleep(10)
                body = page.evaluate("document.body ? document.body.innerText : ''")
                print(f'After name submit: {body[:300]}')
                if 'ERR-837' in body:
                    print('[FAIL] ERR-837')
                elif 'password' in body.lower():
                    print('[SUCCESS] On password page!')
                break
        else:
            print('No visible text input found')
            # List all inputs
            all_inputs = page.locator('input').all()
            for inp in all_inputs:
                vis = inp.is_visible() if inp.is_attached() else 'N/A'
                print(f'  Input: type={inp.get_attribute("type")}, visible={vis}')
    
    ctx.close()
    browser.close()
