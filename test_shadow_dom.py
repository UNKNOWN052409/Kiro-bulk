"""Check for Shadow DOM content."""
from playwright.sync_api import sync_playwright
import time

js_check = """
() => {
    const results = {
        bodyChildren: document.body ? document.body.children.length : 0,
        bodyHTML: document.body ? document.body.innerHTML.substring(0, 200) : '',
        hasShadowRoots: false,
        shadowContent: [],
        iframes: [],
        scripts: document.scripts.length,
        readyState: document.readyState
    };
    
    // Check for shadow roots
    const all = document.querySelectorAll('*');
    for (const el of all) {
        if (el.shadowRoot) {
            results.hasShadowRoots = true;
            const text = el.shadowRoot.textContent || '';
            results.shadowContent.push(text.substring(0, 100));
        }
    }
    
    // Check iframes
    const frames = document.querySelectorAll('iframe');
    for (const f of frames) {
        results.iframes.push({src: f.src, id: f.id});
    }
    
    return results;
}
"""

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    context = browser.contexts[0]
    page = context.new_page()
    
    page.goto('https://view.awsapps.com/start/', wait_until='domcontentloaded', timeout=30000)
    time.sleep(20)
    
    try:
        results = page.evaluate(js_check)
        print(f"Body children: {results['bodyChildren']}")
        print(f"Body HTML (first 200): {results['bodyHTML']}")
        print(f"Has shadow roots: {results['hasShadowRoots']}")
        print(f"Shadow content: {results['shadowContent'][:3]}")
        print(f"Iframes: {results['iframes']}")
        print(f"Scripts: {results['scripts']}")
        print(f"Ready state: {results['readyState']}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Also check console for errors
    page.close()
    context.close()
