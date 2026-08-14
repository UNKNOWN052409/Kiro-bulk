"""Check raw HTML of the login page."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Navigate to the login page directly
    print("Navigating to signin.aws login page...")
    page.goto('https://us-east-1.signin.aws/platform/d-9067642ac7/login', wait_until='domcontentloaded', timeout=30000)
    time.sleep(10)
    
    # Get raw HTML
    html = page.content()
    print(f"HTML length: {len(html)}")
    print(f"HTML preview: {html[:500]}")
    print()
    
    # Check for specific elements
    print("Checking for input elements:")
    try:
        inputs = page.locator('input').all()
        print(f"  Total inputs: {len(inputs)}")
        for inp in inputs:
            try:
                t = inp.get_attribute('type')
                print(f"    type={t}")
            except:
                pass
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\nChecking for buttons:")
    try:
        btns = page.locator('button').all()
        print(f"  Total buttons: {len(btns)}")
        for b in btns:
            try:
                t = b.inner_text()
                print(f"    text={t}")
            except:
                pass
    except Exception as e:
        print(f"  Error: {e}")
    
    # Check iframes
    print("\nChecking for iframes:")
    try:
        frames = page.frames
        print(f"  Total frames: {len(frames)}")
        for f in frames:
            print(f"    URL: {f.url[:80]}")
            try:
                inputs = f.locator('input').all()
                print(f"    Inputs in frame: {len(inputs)}")
            except:
                pass
    except Exception as e:
        print(f"  Error: {e}")
    
    page.close()
    context.close()
