"""Check network requests on the SSO portal."""
from playwright.sync_api import sync_playwright
import time

requests_log = []

def on_request(request):
    requests_log.append({
        'url': request.url[:100],
        'method': request.method,
        'status': None
    })

def on_response(response):
    for r in requests_log:
        if r['url'] in response.url[:100]:
            r['status'] = response.status

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.on('request', on_request)
    page.on('response', on_response)
    
    print("Navigating to SSO portal...")
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(15)
    
    print(f"Total requests: {len(requests_log)}")
    print("\nFirst 20 requests:")
    for r in requests_log[:20]:
        print(f"  [{r['method']}] {r['url']} -> {r['status']}")
    
    # Check for failed requests
    failed = [r for r in requests_log if r['status'] and r['status'] >= 400]
    print(f"\nFailed requests: {len(failed)}")
    for r in failed[:10]:
        print(f"  [{r['status']}] {r['url']}")
    
    page.close()
    context.close()
