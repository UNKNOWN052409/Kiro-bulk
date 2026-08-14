"""Debug: check iframes and shadow DOMs on the AWS page."""
import time, uuid
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
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': 1366, 'height': 768})
        page = context.new_page()
        
        try:
            page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                      wait_until='commit', timeout=30000)
        except Exception:
            pass
        
        time.sleep(15.0)
        
        # Comprehensive check
        results = page.evaluate("""() => {
            const r = {};
            r.url = window.location.href;
            r.readyState = document.readyState;
            r.bodyText = document.body ? document.body.innerText : '';
            r.mainContainer = document.querySelector('#main-container') ? document.querySelector('#main-container').outerHTML.substring(0, 500) : 'NO MC';
            
            // Check all elements
            r.allElements = document.querySelectorAll('*').length;
            r.divs = document.querySelectorAll('div').length;
            r.inputs = document.querySelectorAll('input').length;
            r.buttons = document.querySelectorAll('button').length;
            r.links = document.querySelectorAll('a').length;
            
            // Check iframes
            r.iframes = Array.from(document.querySelectorAll('iframe')).map(f => f.src || f.name || 'no-src');
            
            // Check shadow roots
            r.shadowRoots = [];
            document.querySelectorAll('*').forEach(el => {
                if (el.shadowRoot) {
                    r.shadowRoots.push({tag: el.tagName, text: el.shadowRoot.textContent ? el.shadowRoot.textContent.substring(0, 100) : ''});
                }
            });
            
            return r;
        }""")
        
        print(f"URL: {results['url']}")
        print(f"readyState: {results['readyState']}")
        print(f"bodyText: '{results['bodyText'][:100]}'")
        print(f"allElements: {results['allElements']}, divs: {results['divs']}, inputs: {results['inputs']}, buttons: {results['buttons']}, links: {results['links']}")
        print(f"iframes: {results['iframes']}")
        print(f"shadowRoots: {results['shadowRoots']}")
        print(f"mainContainer: {results['mainContainer'][:200]}")
        
        # Take screenshot
        page.screenshot(path='/tmp/aws_page_debug.png')
        print("Screenshot saved to /tmp/aws_page_debug.png")
        
        page.close()
        context.close()
        browser.close()

main()
