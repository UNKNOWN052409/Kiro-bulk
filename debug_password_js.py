"""Debug: try setting password values via JavaScript and clicking Continue."""
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
    password = ''.join(random.choice(string.ascii_letters + string.digits + "!@#$") for _ in range(16))
    print(f"Password: {password}")
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
            if 'verify your email' in body:
                break
        
        # Wait for OTP to arrive (use extract_otp_v3)
        from extract_otp_v3 import extract_otp_gmail_v3
        otp_arrival = time.time()
        otp = None
        for attempt in range(12):
            time.sleep(8.0)
            otp = extract_otp_gmail_v3(email, after_timestamp=otp_arrival - 300)
            if otp:
                break
        
        if otp:
            print(f"[+] OTP: {otp}")
            inp = page.locator('input:not([type="password"]):visible')
            inp.click()
            inp.fill(otp)
            inp.press('Enter')
            print("[+] OTP submitted")
            time.sleep(15.0)
            
            # Confirm
            try:
                page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                print("[+] Confirm clicked")
                time.sleep(15.0)
            except Exception:
                pass
        else:
            print("[!] No OTP - stopping")
            page.close(); context.close()
            return
        
        # Password creation page
        body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
        print(f"Body: {body[:200]}")
        
        if 'create your password' in body.lower():
            print("[*] Trying JS-based password fill...")
            
            # Use JS to set the values and dispatch input events
            js_result = safe_eval(page, f"""
                const inputs = document.querySelectorAll('input[type="password"]');
                let results = [];
                inputs.forEach((input, index) => {{
                    // Use native input setter to bypass React
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeSetter.call(input, '{password}');
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    results.push({{index, ok: true, value: input.value}});
                }});
                return results;
            """, [])
            
            print(f"JS fill result: {js_result}")
            time.sleep(3.0)
            
            # Click Continue
            result = safe_eval(page, """
                const btns = Array.from(document.querySelectorAll('button'));
                const continueBtn = btns.find(b => b.innerText.trim() === 'Continue' && b.offsetParent !== null);
                if (continueBtn) {
                    continueBtn.click();
                    return {clicked: true};
                }
                return {clicked: false};
            """, {})
            print(f"Continue click result: {result}")
            time.sleep(15.0)
            
            # Check state
            body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
            print(f"After password+continue: {body[:300]}")
        
        page.close()
        context.close()

main()
