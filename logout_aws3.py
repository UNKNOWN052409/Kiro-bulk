from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    
    # Navigate to SSO portal
    try:
        page.goto('https://view.awsapps.com/start', wait_until='domcontentloaded', timeout=30000)
    except:
        pass
    
    time.sleep(10)
    
    # Check if logged in
    try:
        body = page.evaluate("document.body ? document.body.innerText : ''")
        print(f"Body: {body[:200]}")
        
        if 'Sign out' in body or 'Test' in body or 'Gupta' in body:
            # Click Sign out
            try:
                page.get_by_text('Sign out').click()
                print("Clicked Sign out")
                time.sleep(5)
            except:
                try:
                    page.get_by_role('link', name='Sign out').click()
                    print("Clicked Sign out (link)")
                    time.sleep(5)
                except:
                    print("Could not click Sign out")
    except Exception as e:
        print(f"Error: {e}")
    
    # Navigate to OIDC authorize to see if we're logged out
    try:
        page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
        time.sleep(2)
    except:
        pass
    
    context.close()
    print("Done!")
