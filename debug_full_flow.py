"""Full debug flow - go through all steps and check what happens at each."""
import time, uuid, string, random
import boto3
from playwright.sync_api import sync_playwright

def safe_eval(page, js, default=None):
    try:
        return page.evaluate(js)
    except Exception:
        return default

def main():
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
    
    email = f"{''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))}@havenhaus.in"
    password = 'TestPass1234abcd'
    name = email.split('@')[0]
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                  wait_until='commit', timeout=60000)
        
        # Wait for content
        for i in range(20):
            time.sleep(1.0)
            body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
            if body and len(body) > 30:
                break
        
        # Handle cookies
        try:
            page.locator('button:has-text("Decline")').first.click(timeout=3000)
        except Exception:
            pass
        time.sleep(2.0)
        
        # Device continue
        page.locator('button:has-text("Continue")').first.click(timeout=5000)
        time.sleep(5.0)
        
        # Fill email
        inp = page.locator('input:not([type="password"]):visible')
        inp.click()
        inp.fill(email)
        inp.press('Enter')
        print("[+] Email submitted")
        
        # Wait for name page
        for _ in range(20):
            time.sleep(1.0)
            body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
            if 'enter your name' in body:
                break
        
        # Fill name
        inp = page.locator('input:not([type="password"]):visible')
        inp.click()
        inp.type(name.title(), delay=100)
        time.sleep(1.0)
        page.locator('button:has-text("Continue")').first.click(timeout=5000)
        print("[+] Name submitted")
        
        # Wait for OTP page
        for _ in range(20):
            time.sleep(1.0)
            body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
            if 'verify your email' in body or 'verification code' in body:
                break
        
        print("[*] Waiting for OTP (check Gmail)...")
        # Wait 60 seconds for OTP to arrive
        time.sleep(60)
        
        # Check for OTP manually - just print the body to see if we need to enter it
        body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
        print(f"Body: {body[:200]}")
        
        # Don't actually enter OTP - just observe the state
        print("[*] Stopping here for debugging")
        
        page.close()
        context.close()

main()
