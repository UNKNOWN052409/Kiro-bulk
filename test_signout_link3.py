"""Find the Sign out link on the SSO portal."""
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
    
    print(f"URL: {page.url}")
    
    body = safe_eval(page, "document.body ? document.body.innerText : ''")
    print(f"Body: {body[:200] if body else 'N/A'}")
    
    links = safe_eval(page, "Array.from(document.querySelectorAll('a')).map(a => ({text: a.textContent.trim(), href: a.href}))")
    if links:
        for link in links:
            if link['text']:
                print(f"  Link: '{link['text'][:30]}' -> {link['href'][:100]}")
    
    page.close()
    context.close()
