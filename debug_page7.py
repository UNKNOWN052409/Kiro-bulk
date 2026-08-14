"""Debug: check main-container content with different methods."""
from playwright.sync_api import sync_playwright
import time

def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto('https://view.awsapps.com/start/#/device?user_code=TEST-TEST',
                      wait_until='commit', timeout=30000)
        except Exception:
            pass
        
        time.sleep(10.0)
        
        # Multiple ways to get content
        results = page.evaluate("""() => {
            const mc = document.querySelector('#main-container');
            return {
                mcHTML: mc ? mc.innerHTML : 'NO MC',
                mcChildren: mc ? mc.children.length : 0,
                bodyChildren: document.body.children.length,
                bodyHTML: document.body.innerHTML.substring(0, 500),
                allText: document.documentElement.innerText || '',
            };
        }""")
        
        print(f"mainContainer HTML: {results['mcHTML'][:200]}")
        print(f"mainContainer children: {results['mcChildren']}")
        print(f"body children: {results['bodyChildren']}")
        print(f"body HTML: {results['bodyHTML'][:200]}")
        print(f"allText: {results['allText'][:200]}")
        
        page.close()
        context.close()

main()
