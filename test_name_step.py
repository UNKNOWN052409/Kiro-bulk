"""Test the Name step - check if the script can handle it."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    
    # Check all pages
    for i, page in enumerate(context.pages):
        url = page.url[:80]
        try:
            body = page.evaluate("document.body ? document.body.innerText : ''")
            print(f"Page {i}: {url}")
            print(f"  Body: {body[:200]}")
            
            # Check for name input
            try:
                name_inputs = page.locator('input[name="name"]').all()
                visible_name = [inp for inp in name_inputs if inp.is_visible()]
                print(f"  Name inputs: {len(visible_name)}")
                
                # Try all text inputs
                text_inputs = page.locator('input[type="text"]').all()
                visible_text = [inp for inp in text_inputs if inp.is_visible()]
                print(f"  Text inputs: {len(visible_text)}")
                for inp in visible_text:
                    ph = inp.get_attribute('placeholder')
                    print(f"    placeholder: {ph}")
                
                # Try all inputs regardless of type
                all_inputs = page.locator('input').all()
                visible_all = [inp for inp in all_inputs if inp.is_visible()]
                print(f"  All visible inputs: {len(visible_all)}")
                for inp in visible_all:
                    inp_type = inp.get_attribute('type') or 'text'
                    ph = inp.get_attribute('placeholder')
                    print(f"    type={inp_type}, placeholder={ph}")
            except Exception as e:
                print(f"  Error: {e}")
            
            print()
        except Exception as e:
            print(f"Page {i}: Error - {e}")
    
    context.close()
