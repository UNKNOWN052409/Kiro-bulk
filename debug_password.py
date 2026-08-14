"""Debug the password page - check what happens after filling and clicking Continue."""
import time, uuid, string, random
import boto3
from playwright.sync_api import sync_playwright

def safe_eval(page, js, default=None):
    try:
        return page.evaluate(js)
    except Exception:
        return default

def find_password_input(page, index=0):
    try:
        inp = page.locator('input[type="password"]:visible').nth(index)
        inp.wait_for(timeout=5000)
        if inp.is_visible():
            return inp
    except Exception:
        pass
    return None

def main():
    # Use the same user code from the previous run (might still be valid)
    # Actually, let's start fresh
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
    
    password = ''.join(random.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(16))
    
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
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
        except Exception:
            pass
        time.sleep(5.0)
        
        # Check state
        body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
        print(f"After device continue: {body[:200]}")
        
        page.close()
        context.close()

main()
