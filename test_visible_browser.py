"""Test AWS SSO with non-headless browser on Xvfb."""
import time, uuid, os, subprocess

import boto3
from playwright.sync_api import sync_playwright

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
    
    # Start Xvfb
    xvfb = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1366x768x24'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                ],
                env={**os.environ, 'DISPLAY': ':99'}
            )
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            messages = []
            page.on("console", lambda msg: messages.append(f"{msg.type}: {msg.text[:80]}"))
            
            try:
                page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                          wait_until='commit', timeout=30000)
            except Exception as e:
                print(f"Goto: {e}")
            
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
                mc = page.evaluate("document.querySelector('#main-container') ? document.querySelector('#main-container').innerHTML : 'EMPTY'")
                print(f"mainContainer: '{mc[:200]}'")
                url = page.evaluate("window.location.href")
                print(f"URL: {url}")
                ready = page.evaluate("document.readyState")
                print(f"readyState: {ready}")
                if messages:
                    print(f"Console: {messages[:5]}")
            
            page.close()
            context.close()
            browser.close()
    finally:
        xvfb.terminate()
        xvfb.wait()

main()
