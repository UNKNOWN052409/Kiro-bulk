"""Debug script to check what happens after clicking Confirm and continue."""
import sys, os, time, uuid, boto3
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

def safe_eval(page, js, default=None):
    try:
        return page.evaluate(js)
    except Exception:
        return default

def get_state(page):
    body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
    return {
        'body': body or '',
        'onName': 'enter your name' in body,
        'onOtp': 'verify your email' in body or 'verification code' in body,
        'onPasswordCreate': 'create your password' in body,
        'onAllow': 'allow' in body or 'authorization requested' in body or 'confirm this code' in body,
        'onErr': 'err-837' in body,
    }

def find_input(page):
    for sel in ['input:not([type="password"]):visible', 'input[type="email"]:visible', 'input[type="text"]:visible', 'input:visible']:
        try:
            inp = page.locator(sel).first
            inp.wait_for(timeout=3000)
            if inp.is_visible():
                return inp
        except Exception:
            continue
    return None

email = sys.argv[1] if len(sys.argv) > 1 else "testpy021@havenhaus.in"
name = "Test User"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    context = browser.contexts[0]
    page = context.new_page()
    
    # Device auth
    client = boto3.client('sso-oidc', region_name='us-east-1')
    reg = client.register_client(clientName=f'kiro-{uuid.uuid4().hex[:8]}', clientType='public')
    device = client.start_device_authorization(
        clientId=reg['clientId'], clientSecret=reg['clientSecret'],
        startUrl='https://view.awsapps.com/start'
    )
    user_code = device['userCode']
    print(f"[*] User Code: {user_code}")
    
    # Navigate to device page
    page.goto(f"https://view.awsapps.com/start/#/device?user_code={user_code}", wait_until='domcontentloaded')
    time.sleep(5)
    
    # Check what's on the device page
    body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
    print(f"Device page body: {body[:200]}")
    
    # List all buttons on device page
    buttons = safe_eval(page, "Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')", '')
    print(f"Device page buttons: {buttons}")
    
    # Try multiple selectors for the Continue button
    clicked = False
    for sel in ["button:has-text('Continue')", "button:text('Continue')", "button:has-text('I already have the code')", "button"]:
        try:
            page.locator(sel).first.click(timeout=5000)
            print(f"[+] Device Continue clicked via '{sel}'")
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        # Try clicking any visible button
        try:
            all_btns = page.locator('button:visible').all()
            if all_btns:
                all_btns[0].click(timeout=5000)
                print(f"[+] Clicked first visible button")
                clicked = True
        except Exception:
            pass
    if not clicked:
        print("[!] Could not click device page button - proceeding anyway")
    time.sleep(3)
    
    # Handle cookies
    try:
        page.locator('button:has-text("Decline")').first.click(timeout=3000)
        print("[+] Cookies declined")
    except Exception:
        pass
    time.sleep(2)
    
    # Fill email
    inp = find_input(page)
    if inp:
        inp.fill(email)
        inp.press('Enter')
        print(f"[+] Email submitted: {email}")
    time.sleep(3)
    
    state = get_state(page)
    print(f"After email: onName={state['onName']}, body={state['body'][:100]}")
    
    if state['onName']:
        inp = find_input(page)
        if inp:
            inp.fill(name)
            page.locator("button:has-text(\"Continue\")").first.click(timeout=15000)
            print("[+] Name submitted")
        time.sleep(3)
    
    # OTP
    state = get_state(page)
    print(f"After name: onOtp={state['onOtp']}, body={state['body'][:100]}")
    if state['onOtp']:
        otp = extract_otp_gmail_v3(email)
        if otp:
            inp = find_input(page)
            if inp:
                inp.fill(otp)
                inp.press('Enter')
                print(f"[+] OTP submitted: {otp}")
            time.sleep(3)
    
    # Password
    state = get_state(page)
    print(f"After OTP: onPasswordCreate={state['onPasswordCreate']}, body={state['body'][:100]}")
    if state['onPasswordCreate']:
        import string, random
        password = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits + "!@#$%", k=16))
        inputs = page.locator('input[type="password"]:visible').all()
        if inputs:
            inputs[0].fill(password)
            time.sleep(0.5)
            if len(inputs) > 1:
                inputs[1].fill(password)
            inputs[-1].press('Enter')
            print(f"[+] Password filled ({len(password)} chars)")
            time.sleep(3)
    
    # Now check what the Allow page looks like
    state = get_state(page)
    print(f"\n=== ALLOW PAGE DEBUG ===")
    print(f"Body: {state['body'][:300]}")
    print(f"onAllow: {state['onAllow']}")
    
    # List all buttons
    buttons = safe_eval(page, "Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')", '')
    print(f"Buttons: {buttons}")
    
    # Try clicking the first available button
    if 'Confirm and continue' in buttons:
        print("[*] Clicking 'Confirm and continue'...")
        page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
        time.sleep(5)
        
        # Check what happens after
        state2 = get_state(page)
        print(f"\n=== AFTER CONFIRM ===")
        print(f"URL: {page.url}")
        print(f"Body: {state2['body'][:300]}")
        
        # List buttons again
        buttons2 = safe_eval(page, "Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')", '')
        print(f"Buttons: {buttons2}")
        
        if 'Allow' in buttons2 or 'allow' in state2['body'].lower():
            print("[+] Allow page detected! Clicking Allow...")
            try:
                page.locator('button:has-text("Allow")').first.click(timeout=5000)
                print("[+] Allow clicked!")
            except Exception:
                page.keyboard.press('Enter')
                print("[+] Enter pressed!")
            time.sleep(3)
            state3 = get_state(page)
            print(f"\n=== AFTER ALLOW ===")
            print(f"URL: {page.url if 'page3' in dir() else page.url}")
            print(f"Body: {state3['body'][:200]}")
    else:
        print("[!] No Confirm button found")
    
    page.close()
    context.close()
