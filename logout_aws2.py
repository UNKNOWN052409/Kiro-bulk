from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    
    for pg in context.pages[1:]:
        try: pg.close()
        except: pass
    
    page = context.pages[0] if context.pages else context.new_page()
    
    # First go to about:blank
    page.goto('about:blank', wait_until='domcontentloaded', timeout=10000)
    time.sleep(2)
    
    # Then navigate to SSO portal
    page.goto('https://view.awsapps.com/start', wait_until='domcontentloaded', timeout=30000)
    time.sleep(15)
    
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"Body: {body[:300]}")
    
    # Look for Sign out
    if 'Sign out' in body or 'sign out' in body.lower():
        for btn_text in ["Sign out", "sign out"]:
            try:
                btn = page.get_by_role("button", name=btn_text).first
                if btn.is_visible(timeout=3000):
                    btn.click(timeout=5000)
                    print("Clicked Sign out button")
                    time.sleep(8)
                    break
            except Exception as e:
                print(f"  Button error: {e}")
        try:
            link = page.get_by_role("link", name="Sign out").first
            if link.is_visible(timeout=3000):
                link.click(timeout=5000)
                print("Clicked Sign out link")
                time.sleep(8)
        except Exception as e:
            print(f"  Link error: {e}")
    
    # Check final state
    time.sleep(5)
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"\nFinal body: {body[:200]}")
    
    context.close()
