"""Click Sign out on the SSO portal."""
from playwright.sync_api import sync_playwright
import time

def safe_eval(page, js):
    try:
        return page.evaluate(js)
    except Exception:
        return None

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=10000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=15000)
    time.sleep(10)
    
    # Dismiss cookies
    for btn_text in ["Decline", "Dismiss"]:
        try:
            btns = page.locator(f'button:has-text("{btn_text}")').all()
            for btn in btns:
                try:
                    if btn.is_visible(timeout=500):
                        btn.click(timeout=1000)
                        time.sleep(0.5)
                except:
                    pass
        except:
            pass
    time.sleep(3)
    
    # Try clicking "Sign out" text
    try:
        # Try various selectors
        for selector in ['text=Sign out', 'button:has-text("Sign out")', 'a:has-text("Sign out")', '[onclick*="signout"]', '[href*="signout"]']:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=1000):
                    el.click(timeout=3000)
                    print(f"[+] Clicked using selector: {selector}")
                    break
            except:
                continue
    except Exception as e:
        print(f"[!] Error: {e}")
    
    time.sleep(5)
    
    body = safe_eval(page, "document.body ? document.body.innerText : ''")
    url = page.url
    print(f"URL after signout: {url}")
    print(f"Body: {body[:200] if body else 'N/A'}")
    
    page.close()
    context.close()
