"""
Test existing havenhaus.in account with better cookie handling.
"""
import sys, os, time, subprocess, re
from playwright.sync_api import sync_playwright

EMAIL = 'nicholas204@havenhaus.in'

def handle_cookies(page):
    """Handle cookie preferences page."""
    body = page.evaluate("document.body.innerText").lower()
    if 'cookie preferences' in body or 'essential cookies' in body:
        try:
            page.locator('button:has-text("Decline")').first.click(timeout=3000)
        except Exception:
            try:
                page.locator('button:has-text("Accept")').first.click(timeout=3000)
            except Exception:
                try:
                    page.locator('button:has-text("Customize")').first.click(timeout=3000)
                except Exception:
                    pass
        time.sleep(5.0)
        return True
    return False

def get_state(page):
    body = page.evaluate("document.body.innerText").lower()
    return {
        'body': body,
        'onName': 'enter your name' in body,
        'onOtp': 'verify your email' in body or 'verification code' in body,
        'onCookies': 'cookie preferences' in body,
    }

def main():
    proc = subprocess.Popen(
        ['kiro-cli', 'login', '--use-device-flow', '--license', 'free'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    code = None
    for i in range(30):
        line = proc.stdout.readline()
        if not line: break
        stripped = re.sub(r'\x1b\[[0-9;]*m', '', line.strip())
        if 'Code:' in stripped:
            code = stripped.split('Code:')[1].strip()
            break
        time.sleep(1)
    
    if not code:
        print("[!] No code"); proc.kill(); return
    
    print(f"[*] Code: {code}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        url = f'https://view.awsapps.com/start/#/device?user_code={code}'
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        
        # Handle cookies at any point
        handle_cookies(page)
        
        # Continue on device page
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
        except Exception: pass
        time.sleep(8.0)
        
        # Handle cookies again if they appeared after Continue
        handle_cookies(page)
        
        # Fill email
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.click()
            inp.fill(EMAIL)
            inp.press('Enter')
        except Exception as e:
            print(f"[!] Email: {e}")
        time.sleep(12.0)
        
        # Handle cookies again
        handle_cookies(page)
        
        state = get_state(page)
        print(f"[*] After email: onName={state['onName']}, onOtp={state['onOtp']}")
        print(f"[*] Body: {state['body'][:300]}")
        
        # If on name page, try filling name
        if state['onName']:
            print("[*] On name page - filling name...")
            try:
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.type('Nicholas', delay=100)
                time.sleep(1.0)
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                time.sleep(10.0)
                
                state = get_state(page)
                if state['onOtp']:
                    print("[+] Passed name page!")
                elif state['onName']:
                    if 'err-837' in state['body']:
                        print("[!] ERR-837")
                    else:
                        print("[!] Still on name page")
            except Exception as e:
                print(f"[!] Error: {e}")
        
        if state['onOtp']:
            print("[+] On OTP page - flow works!")
        elif state['onName']:
            print("[!] Still on name page")
        else:
            print("[!] Unknown state")
        
        page.close()
    proc.kill()

if __name__ == '__main__':
    main()
