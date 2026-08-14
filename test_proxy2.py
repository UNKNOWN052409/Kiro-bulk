"""Test AWS SSO through proxy 2 (66.163.118.99)."""
import time, uuid, os, subprocess
import boto3
from playwright.sync_api import sync_playwright

TEST_EMAIL = "testkiro2026@gmail.com"

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
        'onErr': 'err-837' in body,
    }

def find_input(page):
    selectors = ['input:not([type="password"]):visible', 'input[type="email"]:visible', 'input[type="text"]:visible', 'input:visible']
    for sel in selectors:
        try:
            inp = page.locator(sel).first
            inp.wait_for(timeout=5000)
            if inp.is_visible():
                return inp
        except Exception:
            continue
    return None

def handle_cookies(page):
    body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''")
    if body and ('cookie preferences' in body or 'essential cookies' in body):
        try:
            page.locator('button:has-text("Decline")').first.click(timeout=3000)
        except Exception:
            try:
                page.locator('button:has-text("Accept")').first.click(timeout=3000)
            except Exception:
                pass
        time.sleep(3.0)

def main():
    xvfb = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1366x768x24'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        client = boto3.client('sso-oidc', region_name='us-east-1')
        reg = client.register_client(
            clientName=f'kiro-{uuid.uuid4().hex[:8]}',
            clientType='public'
        )
        device = client.start_device_authorization(
            clientId=reg['clientId'],
            clientSecret=reg['clientSecret'],
            startUrl='https://view.awsapps.com/start'
        )
        user_code = device['userCode']
        print(f"User Code: {user_code}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=['--no-sandbox', '--disable-dev-shm-usage',
                      '--proxy-server=socks5://66.163.118.99:10006'],
                env={**os.environ, 'DISPLAY': ':99'}
            )
            context = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = context.new_page()
            
            try:
                page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                          wait_until='commit', timeout=60000)
            except Exception as e:
                print(f"Goto: {e}")
            
            # Wait for content through proxy (slower)
            for i in range(30):
                time.sleep(2.0)
                body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
                if body and len(body) > 30 and 'forbidden' not in body.lower():
                    print(f"Content after {i*2:.0f}s: {body[:150]}")
                    break
            
            handle_cookies(page)
            
            # Check if we're on device page
            body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
            if 'device' in body or 'user code' in body or 'enter code' in body:
                print("[+] On device page")
                try:
                    page.locator('button:has-text("Continue")').first.click(timeout=5000)
                    print("[+] Device Continue clicked")
                except Exception:
                    print("[!] Device Continue failed")
            
            # Wait for email page
            for _ in range(20):
                time.sleep(2.0)
                body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
                if body and 'email' in body:
                    break
            
            inp = find_input(page)
            if inp:
                inp.click()
                inp.press('Control+a')
                inp.press('Backspace')
                inp.fill(TEST_EMAIL)
                inp.press('Enter')
                print("[+] Email submitted")
            
            state = None
            for _ in range(20):
                time.sleep(2.0)
                state = get_state(page)
                if state['onName'] or state['onOtp'] or state['onErr']:
                    break
            
            if not state:
                print("[!] No state detected")
                page.close(); context.close(); browser.close(); xvfb.terminate()
                return
            
            print(f"After email: onName={state['onName']}, onOtp={state['onOtp']}, err={state['onErr']}")
            
            if state['onName']:
                name = TEST_EMAIL.split('@')[0]
                inp = find_input(page)
                if inp:
                    inp.click()
                    inp.type(name.title(), delay=100)
                    time.sleep(1.0)
                    try:
                        page.locator('button:has-text("Continue")').first.click(timeout=5000)
                    except Exception:
                        pass
                    
                    for _ in range(20):
                        time.sleep(2.0)
                        state = get_state(page)
                        if state['onOtp'] or state['onErr']:
                            break
                    
                    print(f"After name: onOtp={state['onOtp']}, err={state['onErr']}")
                    if state['onOtp']:
                        print("[+] SUCCESS! Name page passed through proxy!")
                    if state['onErr']:
                        print("[!] ERR-837 even through proxy")
            
            page.close()
            context.close()
            browser.close()
    finally:
        xvfb.terminate()
        xvfb.wait()

main()
