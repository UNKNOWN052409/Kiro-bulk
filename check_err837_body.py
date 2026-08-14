"""Check what the body looks like when ERR-837 is detected."""
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
    name = email.split('@')[0]
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                  wait_until='commit', timeout=60000)
        
        for i in range(20):
            time.sleep(1.0)
            body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
            if body and len(body) > 30:
                break
        
        try:
            page.locator('button:has-text("Decline")').first.click(timeout=3000)
        except Exception:
            pass
        time.sleep(2.0)
        
        page.locator('button:has-text("Continue")').first.click(timeout=5000)
        time.sleep(5.0)
        
        inp = page.locator('input:not([type="password"]):visible')
        inp.click()
        inp.fill(email)
        inp.press('Enter')
        
        # Wait for name page or OTP
        for _ in range(30):
            time.sleep(1.0)
            body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
            bl = body.lower()
            if 'enter your name' in bl or 'verify your email' in bl or 'verification code' in bl:
                break
        
        # Print the full body to see what's there
        body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
        print(f"=== FULL BODY ===")
        print(body)
        print(f"=== END ===")
        
        # Also check for err-837 anywhere in HTML
        html = safe_eval(page, "document.documentElement.innerHTML", '')
        if 'err-837' in html.lower():
            print("\n[!] Found 'err-837' in HTML")
            # Find the context
            idx = html.lower().find('err-837')
            print(f"Context: ...{html[max(0,idx-200):idx+200]}...")
        else:
            print("\n[+] No 'err-837' in HTML")
        
        # If on name page, try submitting
        if 'enter your name' in body.lower():
            inp = page.locator('input:not([type="password"]):visible')
            inp.click()
            inp.type(name.title(), delay=100)
            time.sleep(1.0)
            try:
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                print("\n[+] Name submitted - checking result...")
                time.sleep(5.0)
                body2 = safe_eval(page, "document.body ? document.body.innerText : ''", '')
                print(f"=== BODY AFTER NAME SUBMIT ===")
                print(body2)
                print(f"=== END ===")
            except Exception:
                pass
        
        page.close()
        context.close()

main()
