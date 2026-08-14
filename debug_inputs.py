"""Debug: check all inputs on the password page."""
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
        
        for _ in range(20):
            time.sleep(1.0)
            body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
            if 'enter your name' in body:
                break
        
        inp = page.locator('input:not([type="password"]):visible')
        inp.click()
        inp.type(name.title(), delay=100)
        time.sleep(1.0)
        page.locator('button:has-text("Continue")').first.click(timeout=5000)
        
        for _ in range(20):
            time.sleep(1.0)
            body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
            if 'verify your email' in body:
                break
        
        # Wait for OTP
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
            time.sleep(15.0)
            try:
                page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                time.sleep(15.0)
            except Exception:
                pass
        else:
            print("[!] No OTP")
            page.close(); context.close()
            return
        
        # Check ALL inputs on password page
        all_inputs = safe_eval(page, """
            Array.from(document.querySelectorAll('input')).map(i => ({
                type: i.type,
                name: i.name,
                id: i.id,
                visible: i.offsetParent !== null,
                placeholder: i.getAttribute('placeholder'),
                ariaLabel: i.getAttribute('aria-label'),
                class: i.className
            }))
        """, [])
        print(f"All inputs: {all_inputs}")
        
        # Check shadow DOMs
        shadow_info = safe_eval(page, """
            const results = [];
            const allEls = document.querySelectorAll('*');
            allEls.forEach(el => {
                if (el.shadowRoot) {
                    const shadowInputs = el.shadowRoot.querySelectorAll('input');
                    shadowInputs.forEach(si => {
                        results.push({
                            host: el.tagName,
                            type: si.type,
                            name: si.name
                        });
                    });
                }
            });
            return results;
        """, [])
        print(f"Shadow DOM inputs: {shadow_info}")
        
        page.close()
        context.close()

main()
