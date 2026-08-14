"""Test AWS SSO through proxy with longer waits."""
import time, uuid, subprocess
import boto3
from playwright.sync_api import sync_playwright

def safe_eval(page, js, default=None):
    try:
        return page.evaluate(js)
    except Exception:
        return default

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
                      '--proxy-server=socks5://45.194.33.12:30001',
                      '--proxy-bypass-list=<-loopback>'],
                env={**__import__('os').environ, 'DISPLAY': ':99'}
            )
            context = browser.new_context(viewport={'width': 1366, 'height': 768})
            page = context.new_page()
            
            # Navigate with longer timeout
            try:
                page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                          wait_until='commit', timeout=60000)
                print("[+] Page navigation started")
            except Exception as e:
                print(f"Goto: {e}")
            
            # Wait much longer for content through proxy
            for i in range(40):
                time.sleep(1.5)
                body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
                if body and len(body) > 30:
                    print(f"Content after {i*1.5:.0f}s: {body[:150]}")
                    break
            else:
                body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
                url = safe_eval(page, "window.location.href", '')
                print(f"After 60s: body='{body[:100]}', url={url}")
            
            page.close()
            context.close()
            browser.close()
    finally:
        xvfb.terminate()
        xvfb.wait()

main()
