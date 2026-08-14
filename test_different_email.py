"""
Test if ERR-837 is domain-specific by using a different email.
"""
import sys, os, time, subprocess, re
from playwright.sync_api import sync_playwright

# Use a test Gmail address
EMAIL = 'kirotest2026@gmail.com'

def main():
    # Start kiro-cli
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
        print(f"[*] After email: {body[:200]}")
        
        if 'enter your name' in body:
            print("[*] On name page with different email...")
            try:
                inp = page.locator('input:not([type="password"]):visible').first
                inp.click()
                inp.type('John Smith', delay=100)
                time.sleep(1.0)
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                time.sleep(10.0)
                
                body = page.evaluate("document.body.innerText").lower()
                if 'enter your name' not in body:
                    print("[+] SUCCESS - passed name page!")
                    print(f"[*] Body: {body[:300]}")
                elif 'err-837' in body:
                    print("[!] ERR-837 even with different email domain")
                else:
                    print(f"[!] Still on name page")
            except Exception as e:
                print(f"[!] Error: {e}")
        elif 'verify' in body:
            print("[+] SKIPPED name page - went directly to OTP!")
        else:
            print(f"[!] Unexpected: {body[:200]}")
        
        page.close()
    
    proc.kill()

if __name__ == '__main__':
    main()
