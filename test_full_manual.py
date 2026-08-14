"""Test the full flow manually to understand the page transitions."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    
    for pg in context.pages[1:]:
        try: pg.close()
        except: pass
    
    page = context.pages[0]
    
    # STEP 1: Check current state (should be login page)
    print("[*] Current state:")
    page.evaluate("document.readyState")
    body = page.evaluate("document.body.innerText")
    print(f"  Body: {body[:200]}")
    
    # Wait for render
    for _ in range(30):
        time.sleep(2)
        ready = page.evaluate("document.readyState")
        body = page.evaluate("document.body.innerText")
        if ready == 'complete' and len(body) > 50:
            break
    print(f"  Ready: {ready}, Body len: {len(body)}")
    
    # STEP 2: Fill email and click Continue
    print("\n[*] STEP 2: Fill email")
    email_inputs = page.locator('input').all()
    visible = [inp for inp in email_inputs if inp.is_visible()]
    print(f"  Visible inputs: {len(visible)}")
    for inp in visible:
        inp_type = inp.get_attribute('type') or 'text'
        print(f"    type={inp_type}, placeholder={inp.get_attribute('placeholder')}")
    
    if visible:
        visible[0].fill("test-manual-flow@havenhaus.in")
        time.sleep(1)
        print("  Email filled")
        
        # Click Continue
        try:
            btn = page.get_by_role("button", name="Continue").first
            btn.click(timeout=5000)
            print("  Continue clicked")
        except Exception as e:
            print(f"  Error: {e}")
    
    # Wait for next page
    print("\n[*] Waiting for next page...")
    for i in range(30):
        time.sleep(3)
        try:
            ready = page.evaluate("document.readyState")
            body = page.evaluate("document.body.innerText")
            url = page.url[:80]
            print(f"  [{i*3}s] URL: {url} | Ready: {ready} | Body: {body[:100]}")
            
            if 'Enter your name' in body or 'Create your password' in body or 'Allow' in body:
                print(f"  *** Found target page! ***")
                break
            if 'Get started' in body and len(body) > 50:
                # Still on email page, wait more
                pass
        except Exception as e:
            print(f"  Error: {e}")
    
    context.close()
