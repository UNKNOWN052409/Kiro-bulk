"""
Test if an existing havenhaus.in account skips the name page.
Use nicholas204@havenhaus.in which was already successfully added before.
"""
import sys, os, time, subprocess, re
from playwright.sync_api import sync_playwright

EMAIL = 'nicholas204@havenhaus.in'

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
    print(f"[*] Email: {EMAIL}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        url = f'https://view.awsapps.com/start/#/device?user_code={code}'
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        
        # Handle cookies
        body = page.evaluate("document.body.innerText").lower()
        if 'cookie' in body:
            try:
                page.locator('button:has-text("Decline")').first.click(timeout=3000)
            except Exception:
                try:
                    page.locator('button:has-text("Accept")').first.click(timeout=3000)
                except Exception:
                    pass
            time.sleep(3.0)
        
        # Continue
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
        except Exception: pass
        time.sleep(8.0)
        
        # Fill email
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.click()
            inp.fill(EMAIL)
            inp.press('Enter')
        except Exception as e:
            print(f"[!] Email: {e}")
        time.sleep(12.0)
        
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] After email: {body[:300]}")
        
        if 'enter your name' in body:
            print("[!] Existing account still shows name page - trying name anyway...")
            try:
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.type('Nicholas', delay=100)
                time.sleep(1.0)
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                time.sleep(10.0)
                
                body = page.evaluate("document.body.innerText").lower()
                if 'enter your name' not in body:
                    print("[+] Passed name page!")
                elif 'err-837' in body:
                    print("[!] ERR-837 even for existing account")
                else:
                    print(f"[*] Body: {body[:200]}")
            except Exception as e:
                print(f"[!] Error: {e}")
        elif 'verify' in body or 'otp' in body:
            print("[+] Skipped name page - existing account!")
        else:
            print(f"[!] Unexpected state")
        
        page.close()
    proc.kill()

if __name__ == '__main__':
    main()
