"""Fill OTP on the verification page."""
from playwright.sync_api import sync_playwright
import time, sys, re

sys.path.insert(0, '/home/ubuntu/kiro-gen')
from extract_otp_v3 import extract_otp_gmail_v3

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.pages[0]
    
    body = page.evaluate("document.body.innerText")
    print(f"Body: {body[:200]}")
    
    email_match = re.search(r'(\w+@havenhaus\.in)', body)
    email = email_match.group(1) if email_match else None
    print(f"Email: {email}")
    
    if email:
        otp = extract_otp_gmail_v3(email)
        print(f"OTP: {otp}")
        
        if otp:
            text_inputs = page.locator('input').all()
            visible = [inp for inp in text_inputs if inp.is_visible()]
            print(f"Visible inputs: {len(visible)}")
            for inp in visible:
                inp_type = inp.get_attribute('type') or 'text'
                print(f"  type={inp_type}, placeholder={inp.get_attribute('placeholder')}")
            
            # Fill any visible text input
            for inp in visible:
                inp_type = inp.get_attribute('type') or 'text'
                if inp_type == 'text':
                    inp.fill(otp)
                    print(f"Filled OTP in text input")
                    break
            
            time.sleep(2)
            
            for btn_text in ["Verify", "Continue", "Submit"]:
                try:
                    btn = page.get_by_role("button", name=btn_text).first
                    if btn.is_visible(timeout=3000):
                        btn.click(timeout=5000)
                        print(f"Clicked: {btn_text}")
                        break
                except:
                    pass
    
    # Wait for next page
    for i in range(20):
        time.sleep(3)
        try:
            body = page.evaluate("document.body.innerText")
            print(f"\n[{i * 3}s] Body: {body[:200]}")
            if 'Allow' in body or 'allow access' in body.lower():
                print("*** On Allow page! ***")
                # Click Allow
                for btn_text in ["Allow access", "Allow"]:
                    try:
                        btn = page.get_by_role("button", name=btn_text).first
                        if btn.is_visible(timeout=3000):
                            btn.click(timeout=5000)
                            print(f"Clicked: {btn_text}")
                            break
                    except:
                        pass
                break
        except Exception as e:
            print(f"Error: {e}")
    
    context.close()
