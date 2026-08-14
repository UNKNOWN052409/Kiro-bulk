"""Fix the script and test with current browser state."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    
    # Close extra pages
    for pg in context.pages[1:]:
        try: pg.close()
        except: pass
    
    page = context.pages[0] if context.pages else context.new_page()
    
    # Wait for page to load
    for _ in range(30):
        time.sleep(2)
        try:
            body = page.evaluate("document.body.innerText")
            if len(body) > 50:
                print(f"Page loaded: {body[:100]}")
                break
        except:
            pass
    
    # Fill name (if on name page) or email (if on login page)
    body = page.evaluate("document.body.innerText")
    body_lower = body.lower()
    print(f"\nCurrent body: {body[:150]}")
    
    if 'enter your name' in body_lower:
        print("On Name page!")
        text_inputs = page.locator('input').all()
        visible = [inp for inp in text_inputs if inp.is_visible()]
        print(f"Visible inputs: {len(visible)}")
        for inp in visible:
            print(f"  type={inp.get_attribute('type')}, placeholder={inp.get_attribute('placeholder')}")
        if visible:
            visible[0].fill("Manual Test User")
            time.sleep(1)
            try:
                page.get_by_role("button", name="Continue").first.click(timeout=5000)
                print("Continue clicked")
            except Exception as e:
                print(f"Error: {e}")
    
    context.close()
