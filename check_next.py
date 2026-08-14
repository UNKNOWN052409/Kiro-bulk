from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.pages[0]
    
    for _ in range(30):
        time.sleep(3)
        try:
            body = page.evaluate("document.body.innerText")
            url = page.url[:80]
            print(f"[{_ * 3}s] URL: {url}")
            print(f"  Body: {body[:200]}")
            
            if 'Create your password' in body or 'password' in body.lower() and 'sign in' not in body.lower()[:50]:
                print("  *** On password page! ***")
                # Fill password
                pw_inputs = page.locator('input').all()
                visible = [inp for inp in pw_inputs if inp.is_visible() and inp.get_attribute('type') == 'password']
                print(f"  Password inputs: {len(visible)}")
                if visible:
                    visible[0].fill("TestPass9999!")
                    if len(visible) > 1:
                        visible[1].fill("TestPass9999!")
                    time.sleep(1)
                    try:
                        page.get_by_role("button", name="Continue").first.click(timeout=5000)
                        print("  Continue clicked!")
                    except Exception as e:
                        print(f"  Error: {e}")
                break
            if 'verification' in body.lower() or 'one-time' in body.lower():
                print("  *** On OTP page! ***")
                break
            if 'Allow' in body:
                print("  *** On Allow page! ***")
                break
        except Exception as e:
            print(f"  Error: {e}")
    
    context.close()
