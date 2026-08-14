"""Debug: test with a real user code."""
import sys, time, uuid
import boto3
from playwright.sync_api import sync_playwright

def main():
    # Get a real user code
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
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        # Collect console messages
        messages = []
        page.on("console", lambda msg: messages.append(f"{msg.type}: {msg.text[:100]}"))
        
        try:
            page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                      wait_until='commit', timeout=30000)
        except Exception:
            pass
        
        # Wait for content to appear
        for i in range(30):
            time.sleep(1.0)
            try:
                text = page.evaluate("document.body ? document.body.innerText : ''")
                if text and len(text) > 10:
                    print(f"After {i+1}s: {text[:200]}")
                    break
            except Exception:
                pass
        else:
            text = page.evaluate("document.body ? document.body.innerText : ''")
            print(f"After 30s: '{text[:100]}'")
            
            # Try innerHTML
            mc = page.evaluate("document.querySelector('#main-container') ? document.querySelector('#main-container').innerHTML : 'EMPTY'")
            print(f"mainContainer: '{mc[:200]}'")
            
            # Check URL
            url = page.evaluate("window.location.href")
            print(f"URL: {url}")
            
            if messages:
                print(f"\nConsole: {messages[:5]}")
        
        page.close()
        context.close()

main()
