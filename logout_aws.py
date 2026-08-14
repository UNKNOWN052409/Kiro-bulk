from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    
    for pg in context.pages[1:]:
        try: pg.close()
        except: pass
    
    page = context.pages[0] if context.pages else context.new_page()
    
    # Navigate to SSO portal to find Sign out
    page.goto('https://view.awsapps.com/start', wait_until='domcontentloaded', timeout=30000)
    time.sleep(10)
    
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"Body: {body[:200]}")
    
    # Try to find Sign out
    if 'Sign out' in body:
        for btn_text in ["Sign out", "sign out"]:
            try:
                btn = page.get_by_role("button", name=btn_text).first
                if btn.is_visible(timeout=3000):
                    btn.click(timeout=5000)
                    print("Clicked Sign out")
                    time.sleep(5)
                    break
            except:
                pass
        # Also try links
        try:
            link = page.get_by_role("link", name="Sign out").first
            if link.is_visible(timeout=3000):
                link.click(timeout=5000)
                print("Clicked Sign out link")
                time.sleep(5)
        except:
            pass
    
    # Check final state
    body = page.evaluate("document.body ? document.body.innerText : ''")
    print(f"\nFinal body: {body[:100]}")
    
    context.close()
