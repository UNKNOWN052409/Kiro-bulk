"""Debug: check what buttons are available on the password page."""
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
    
    password = 'TestPass1234abcd'
    
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
        
        # Check state - get all buttons
        buttons_info = safe_eval(page, """
            Array.from(document.querySelectorAll('button')).map(b => ({
                text: b.innerText.trim(),
                visible: b.offsetParent !== null,
                disabled: b.disabled,
                ariaDisabled: b.getAttribute('aria-disabled')
            }))
        """, [])
        print("Buttons:", buttons_info)
        
        # Check password inputs
        pass_info = safe_eval(page, """
            Array.from(document.querySelectorAll('input[type="password"]')).map(i => ({
                visible: i.offsetParent !== null,
                disabled: i.disabled,
                ariaDisabled: i.getAttribute('aria-disabled'),
                placeholder: i.getAttribute('placeholder')
            }))
        """, [])
        print("Password inputs:", pass_info)
        
        page.close()
        context.close()

main()
