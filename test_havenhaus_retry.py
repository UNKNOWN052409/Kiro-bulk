"""
Retry havenhaus.in after 5 minute wait.
"""
import sys, os, time, subprocess, re
from playwright.sync_api import sync_playwright

EMAIL = 'ax3p0kzyk6@havenhaus.in'

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
        context = browser.new_context()
        page = context.new_page()
        
        page.goto(f'https://view.awsapps.com/start/#/device?user_code={code}', 
                  wait_until='domcontentloaded', timeout=30000)
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
            time.sleep(5.0)
        
        # Continue
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
        except Exception: pass
        time.sleep(8.0)
        
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
            time.sleep(5.0)
        
        # Fill email
        inp = page.locator('input:not([type="password"]):visible').first
        inp.click()
        inp.press('Control+a')
        inp.press('Backspace')
        inp.fill(EMAIL)
        inp.press('Enter')
        time.sleep(12.0)
        
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] After email: {body[:200]}")
        
        if 'enter your name' in body:
            print("[*] On name page - trying name...")
            inp = page.locator('input:not([type="password"]):visible').first
            inp.click()
            inp.type('Test User', delay=100)
            time.sleep(1.0)
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
            time.sleep(10.0)
            
            body = page.evaluate("document.body.innerText").lower()
            if 'enter your name' not in body:
                print("[+] PASSED name page! AWS block lifted!")
            elif 'err-837' in body:
                print("[!] ERR-837 still present")
            else:
                print(f"[*] Unexpected: {body[:200]}")
        elif 'verify' in body:
            print("[+] Skipped name page (existing account?)")
        else:
            print(f"[!] Unexpected: {body[:200]}")
        
        page.close()
        context.close()
    proc.kill()

if __name__ == '__main__':
    main()
