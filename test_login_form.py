"""Check if login form appears after full render."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=30000)
    
    # Wait for full render (50+ seconds)
    print("Waiting for full render...")
    for i in range(15):
        time.sleep(5)
        try:
            ready = page.evaluate("document.readyState")
            if ready == 'complete':
                body = page.evaluate("document.body ? document.body.innerText : ''")
                print(f"[{i*5}s] complete | body: {body[:150]}")
                if len(body) > 100:
                    break
        except:
            pass
    
    # Now check for login elements
    time.sleep(5)
    try:
        body = page.evaluate("document.body ? document.body.innerText : ''")
        print(f"\nFull body text:\n{body}")
    except:
        pass
    
    # Check for inputs
    try:
        inputs = page.locator('input').all()
        print(f"\nInputs found: {len(inputs)}")
        for inp in inputs:
            t = inp.get_attribute('type')
            ph = inp.get_attribute('placeholder')
            print(f"  type={t}, placeholder={ph}")
    except Exception as e:
        print(f"Input error: {e}")
    
    # Check for buttons
    try:
        btns = page.locator('button').all()
        print(f"\nButtons found: {len(btns)}")
        for b in btns:
            t = b.inner_text()
            print(f"  {t}")
    except Exception as e:
        print(f"Button error: {e}")
    
    page.close()
    context.close()
