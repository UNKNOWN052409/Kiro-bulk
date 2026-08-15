#!/usr/bin/env python3
"""Debug the signup page API endpoint"""
import sys
sys.path.insert(0, '/home/ubuntu/kiro-gen')
from playwright.sync_api import sync_playwright
import time

SIGNIN_BASE = 'https://us-east-1.signin.aws/platform/d-9067642ac7'
CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        '/tmp/debug-profile',
        channel='chromium',
        headless=True,
        viewport={'width': 1920, 'height': 1080},
        user_agent=CHROME_UA,
        locale='en-US',
        timezone_id='America/New_York',
        args=['--no-sandbox', '--disable-dev-shm-usage'],
    )
    page = context.pages[0] if context.pages else context.new_page()
    
    # Navigate to signup page (without workflow state)
    signup_url = f'{SIGNIN_BASE}/signup'
    print(f"Navigating to: {signup_url}")
    try:
        page.goto(signup_url, wait_until='load', timeout=30000)
    except:
        try:
            page.goto(signup_url, wait_until='domcontentloaded', timeout=30000)
        except:
            pass
    
    time.sleep(5)
    print(f"On page: {page.url}")
    
    # Test various fetch endpoints
    tests = [
        f'{SIGNIN_BASE}/api/execute',
        f'https://us-east-1.signin.aws/api/execute',
        f'{SIGNIN_BASE}/signup/api/execute',
        'https://profile.aws.amazon.com/api/execute',
    ]
    
    for url in tests:
        print(f"\nTesting: {url}")
        try:
            result = page.evaluate(f"""
                async () => {{
                    try {{
                        const resp = await fetch('{url}', {{
                            method: 'POST',
                            credentials: 'include',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{test: true}})
                        }});
                        return {{status: resp.status, ok: resp.ok}};
                    }} catch(e) {{
                        return {{error: e.toString()}};
                    }}
                }}
            """)
            print(f"  Result: {result}")
        except Exception as e:
            print(f"  Exception: {e}")
    
    # Also try GET on the base
    print(f"\nTesting GET on {SIGNIN_BASE}/api/execute")
    try:
        result = page.evaluate(f"""
            async () => {{
                try {{
                    const resp = await fetch('{SIGNIN_BASE}/api/execute', {{
                        method: 'GET',
                        credentials: 'include',
                    }});
                    return {{status: resp.status, ok: resp.ok, text: await resp.text()}};
                }} catch(e) {{
                    return {{error: e.toString()}};
                }}
            }}
        """)
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  Exception: {e}")
    
    # Check the page's network requests to find the correct API endpoint
    print("\nChecking page resources...")
    try:
        page.goto(signup_url, wait_until='load', timeout=30000)
        time.sleep(3)
    except:
        pass
    
    # Try to find API calls in the page's JS
    try:
        result = page.evaluate("""
            () => {
                // Look for fetch/XHR patterns in the page
                const entries = performance.getEntriesByType('resource');
                const apiCalls = entries.filter(e => e.name.includes('api')).map(e => e.name);
                return apiCalls.slice(0, 20);
            }
        """)
        print(f"  API resources found: {result}")
    except Exception as e:
        print(f"  Exception: {e}")
    
    context.close()
