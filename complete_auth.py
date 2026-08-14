"""Complete the auth flow - with navigation error handling."""
import sys, os, time, string, random
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

user_code = sys.argv[1] if len(sys.argv) > 1 else "GJTZ-GCJP"
email = sys.argv[2] if len(sys.argv) > 2 else "testpy028@havenhaus.in"
name = "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)
print(f"[*] Password: {password}")

def safe_eval(page, js, default=''):
    """Evaluate JS safely, handling navigation errors."""
    try:
        result = page.evaluate(js)
        return result if result is not None else default
    except Exception:
        return default

def wait_for_body(page, min_len=50, max_wait=30):
    """Wait for page body to have content, handling navigation."""
    for _ in range(max_wait):
        body = safe_eval(page, "document.body ? document.body.innerText : ''")
        if body and len(body) > min_len:
            return body
        time.sleep(1)
    return safe_eval(page, "document.body ? document.body.innerText : ''")

def dismiss_cookies(page):
    """Dismiss cookie dialogs."""
    for _ in range(10):
        for btn_text in ["Decline", "Dismiss", "Accept"]:
            try:
                btns = page.locator(f'button:has-text("{btn_text}")').all()
                for btn in btns:
                    try:
                        if btn.is_visible(timeout=1000):
                            btn.click(timeout=2000)
                            time.sleep(0.5)
                    except Exception:
                        pass
            except Exception:
                pass
        time.sleep(1)
        body = safe_eval(page, "document.body ? document.body.innerText : ''")
        if body and len(body) > 50 and 'cookie' not in body.lower()[:100]:
            break
    time.sleep(2)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    
    # Navigate to device page
    page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
              wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    
    body = wait_for_body(page, min_len=30)
    print(f"Device page body: {body[:150]}")
    
    # Click Continue on device page
    clicked = False
    for sel in ['button:has-text("Continue")', 'button:visible']:
        try:
            page.locator(sel).first.click(timeout=10000)
            print(f"[+] Device Continue clicked via '{sel}'")
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        page.keyboard.press('Enter')
        print("[+] Enter pressed on device page")
    
    # Wait for navigation to complete
    time.sleep(8)
    
    # Dismiss cookies
    dismiss_cookies(page)
    
    # Wait for email page
    body = wait_for_body(page, min_len=50)
    print(f"After device continue: {body[:150]}")
    
    # Fill email
    try:
        inp = page.locator('input:not([type="password"]):visible').first
        inp.wait_for(timeout=10000)
        inp.fill(email)
        time.sleep(0.5)
        inp.press('Enter')
        print(f"[+] Email submitted: {email}")
    except Exception as e:
        print(f"[!] Email error: {e}")
    time.sleep(5)
    
    # Dismiss cookies if they appear
    dismiss_cookies(page)
    
    # Wait for name page
    body = wait_for_body(page, min_len=50)
    print(f"After email: {body[:150]}")
    
    # Name
    if 'name' in body.lower():
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.wait_for(timeout=5000)
            inp.fill(name)
            time.sleep(0.5)
            for sel in ['button:has-text("Continue")']:
                try:
                    page.locator(sel).first.click(timeout=3000)
                    print("[+] Name Continue clicked")
                    break
                except Exception:
                    continue
        except Exception as e:
            print(f"[!] Name error: {e}")
        time.sleep(5)
    
    # Dismiss cookies
    dismiss_cookies(page)
    
    # Wait for OTP page
    body = wait_for_body(page, min_len=50)
    print(f"After name: {body[:150]}")
    
    # OTP
    if 'verify' in body.lower() or 'code' in body.lower():
        otp = extract_otp_gmail_v3(email)
        if otp:
            try:
                inp = page.locator('input:visible').first
                inp.fill(otp)
                inp.press('Enter')
                print(f"[+] OTP submitted: {otp}")
            except Exception as e:
                print(f"[!] OTP error: {e}")
            time.sleep(5)
    
    # Dismiss cookies
    dismiss_cookies(page)
    
    # Wait for password page
    body = wait_for_body(page, min_len=50)
    print(f"After OTP: {body[:150]}")
    
    # Password
    if 'password' in body.lower():
        try:
            inputs = page.locator('input[type="password"]:visible').all()
            if inputs:
                inputs[0].fill(password)
                time.sleep(1)
                if len(inputs) > 1:
                    inputs[1].fill(password)
                time.sleep(1)
                for sel in ['button:has-text("Continue")']:
                    try:
                        page.locator(sel).first.click(timeout=3000)
                        print("[+] Password Continue clicked")
                        break
                    except Exception:
                        continue
                else:
                    inputs[-1].press('Enter')
                    print("[+] Password Enter pressed")
        except Exception as e:
            print(f"[!] Password error: {e}")
        time.sleep(5)
    
    # Dismiss cookies
    dismiss_cookies(page)
    
    # Wait for Allow page
    body = wait_for_body(page, min_len=50)
    print(f"\n=== ALLOW PAGE ===")
    print(f"Body: {body[:300]}")
    
    buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
    print(f"Buttons: {buttons}")
    
    # Two-step Allow
    if 'Confirm and continue' in buttons:
        print("[*] Step 1: Clicking Confirm and continue...")
        page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
        time.sleep(8)
        
        body = safe_eval(page, "document.body ? document.body.innerText : ''")
        buttons = safe_eval(page, "Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        print(f"After confirm body: {body[:200]}")
        print(f"After confirm buttons: {buttons}")
        
        if 'Allow' in buttons or ('allow' in body.lower() and 'confirm this code' not in body.lower()):
            print("[*] Step 2: Allow page detected!")
            try:
                page.locator('button:has-text("Allow")').first.click(timeout=5000)
                print("[+] Allow clicked!")
            except Exception:
                page.keyboard.press('Enter')
                print("[+] Enter pressed!")
    elif 'Allow' in buttons:
        print("[*] Clicking Allow...")
        page.locator('button:has-text("Allow")').first.click(timeout=5000)
        print("[+] Allow clicked!")
    elif 'confirm' in body.lower() or 'authorize' in body.lower():
        print("[*] Trying Enter on authorization page...")
        page.keyboard.press('Enter')
        print("[+] Enter pressed!")
    
    time.sleep(10)
    print(f"\nFinal URL: {page.url}")
    body = safe_eval(page, "document.body ? document.body.innerText : ''")
    print(f"Final body: {body[:200]}")
    
    page.close()
    context.close()
