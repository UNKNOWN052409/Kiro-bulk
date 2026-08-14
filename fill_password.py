"""Fill password on the Create your password page."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.pages[0]
    
    body = page.evaluate("document.body.innerText")
    print(f"Body: {body[:100]}")
    
    # Fill password fields
    pw_inputs = page.locator('input').all()
    visible = [inp for inp in pw_inputs if inp.is_visible() and inp.get_attribute('type') == 'password']
    print(f"Password inputs: {len(visible)}")
    
    if len(visible) >= 2:
        visible[0].fill("TestPass9999!")
        visible[1].fill("TestPass9999!")
        print("Both password fields filled")
    elif len(visible) == 1:
        visible[0].fill("TestPass9999!")
        print("Password field filled")
    
    time.sleep(1)
    
    # Click Continue
    try:
        page.get_by_role("button", name="Continue").first.click(timeout=5000)
        print("Continue clicked")
    except Exception as e:
        print(f"Error: {e}")
    
    # Wait for next page
    for i in range(20):
        time.sleep(3)
        try:
            body = page.evaluate("document.body.innerText")
            print(f"\n[{i * 3}s] Body: {body[:200]}")
            if 'Allow' in body or 'allow access' in body.lower():
                print("*** On Allow page! ***")
                for btn_text in ["Allow access", "Allow"]:
                    try:
                        btn = page.get_by_role("button", name=btn_text).first
                        if btn.is_visible(timeout=3000):
                            btn.click(timeout=5000)
                            print(f"Clicked: {btn_text}")
                            break
                    except:
                        pass
                break
        except Exception as e:
            print(f"Error: {e}")
    
    context.close()
