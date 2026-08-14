#!/usr/bin/env python3
"""Combined kiro-cli login + browser auth automation.
Starts kiro-cli login, extracts device code, then automates browser."""
import sys
import os
import time
import re
import subprocess
import imaplib
import email
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

# AWS account
EMAIL = 'ax3p0kzyk6@havenhaus.in'
NAME = 'Ross Espinoza'

def get_device_code():
    """Start kiro-cli login and extract the device code."""
    proc = subprocess.Popen(
        ['kiro-cli', 'login', '--use-device-flow', '--license', 'free'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    # Wait for the code to appear
    code = None
    for i in range(30):
        line = proc.stdout.readline()
        if not line:
            break
        if 'Code:' in line:
            raw_code = line.strip().split('Code:')[1].strip()
            # Strip ANSI escape codes
            code = re.sub(r'\x1b\[[0-9;]*m', '', raw_code).strip()
            print(f"[*] Device code: {code}")
            break
        time.sleep(1)
    
    if not code:
        print("[!] No device code found")
        proc.kill()
        return None, proc
    
    return code, proc

def main():
    # Step 1: Start kiro-cli login
    print("[*] Starting kiro-cli login...")
    code, proc = get_device_code()
    if not code:
        return
    
    verify_url = f'https://view.awsapps.com/start/#/device?user_code={code}'
    print(f"[*] Verification URL: {verify_url}")
    
    # Step 2: Automate browser
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        # Navigate to verification URL
        print("[*] Navigating to device verification...")
        page.goto(verify_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        
        # The page should redirect to sign-in
        current_url = page.url
        print(f"[*] Current URL: {current_url}")
        
        # Try clicking Continue on the device page (if it shows a button)
        clicked_continue = page.evaluate("""() => {
            const btns = document.querySelectorAll('button, a');
            for (const b of btns) {
                const vis = b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled;
                if (!vis) continue;
                const t = (b.textContent || '').trim().toLowerCase();
                if (t.includes('continue')) {
                    b.click();
                    return true;
                }
            }
            return false;
        }""")
        print(f"  [+] Continue clicked on device page: {clicked_continue}")
        time.sleep(8.0)
        
        current_url = page.url
        print(f"[*] Current URL after Continue: {current_url}")
        
        if 'signin' in current_url or 'login' in current_url:
            # Fill email
            page.evaluate(f"""() => {{
                const inputs = document.querySelectorAll('input');
                for (const inp of inputs) {{
                    const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                    if (!vis) continue;
                    const type = (inp.type || '').toLowerCase();
                    if (type === 'email' || type === 'text') {{
                        inp.focus();
                        inp.value = '';
                        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        s.call(inp, '{EMAIL}');
                        inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return true;
                    }}
                }}
                return false;
            }}""")
            print("  [+] Email filled")
            page.keyboard.press('Enter')
            time.sleep(8.0)
            
            # Check for name page
            name_page = page.evaluate("""() => (document.body?.innerText || '').toLowerCase().includes('enter your name')""")
            if name_page:
                print("  [*] Name page detected")
                # Fill name and click continue
                page.evaluate(f"""() => {{
                    const inputs = document.querySelectorAll('input');
                    for (const inp of inputs) {{
                        const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                        if (!vis) continue;
                        const type = (inp.type || '').toLowerCase();
                        if (type === 'text' || type === '') {{
                            inp.focus();
                            inp.value = '';
                            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            s.call(inp, '{NAME}');
                            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return true;
                        }}
                    }}
                    return false;
                }}""")
                time.sleep(1.0)
                page.keyboard.press('Enter')
                print("  [+] Name filled + Enter pressed")
                time.sleep(10.0)
            
            # Check for OTP page
            otp_page = page.evaluate("""() => (document.body?.innerText || '').toLowerCase().includes('verify your email')""")
            if otp_page:
                print("  [*] OTP page detected")
                # Get fresh OTP
                otp_arrival = time.time()
                time.sleep(20.0)  # Wait for email
                otp = extract_otp_gmail(EMAIL, timeout=30, after_timestamp=otp_arrival)
                if otp:
                    print(f"  [+] OTP: {otp}")
                    page.evaluate(f"""() => {{
                        const inputs = document.querySelectorAll('input');
                        for (const inp of inputs) {{
                            const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                            if (!vis) continue;
                            const type = (inp.type || '').toLowerCase();
                            if (type === 'text' || type === 'number' || type === '') {{
                                inp.focus();
                                inp.value = '';
                                const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                s.call(inp, '{otp}');
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                                return true;
                            }}
                        }}
                        return false;
                    }}""")
                    page.keyboard.press('Enter')
                    print("  [+] OTP filled + Enter pressed")
                    time.sleep(10.0)
            
            # Check for Confirm page
            confirm_page = page.evaluate("""() => {
                const body = (document.body?.innerText || '').toLowerCase();
                return body.includes('confirm') && body.includes('continue');
            }""")
            if confirm_page:
                print("  [*] Confirm page detected")
                page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const vis = b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled;
                        if (!vis) continue;
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (t.includes('confirm')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                print("  [+] Confirm clicked")
                time.sleep(10.0)
            
            # Check for Allow page
            allow_page = page.evaluate("""() => {
                const body = (document.body?.innerText || '').toLowerCase();
                return body.includes('allow');
            }""")
            if allow_page:
                print("  [*] Allow page detected")
                page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const vis = b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled;
                        if (!vis) continue;
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (t.includes('allow')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                print("  [+] Allow clicked")
                time.sleep(10.0)
        
        # Check final state
        time.sleep(3.0)
        final_url = page.url
        print(f"[*] Final URL: {final_url}")
        page_text = page.evaluate("() => document.body?.innerText || ''")
        print(f"[*] Page: {page_text[:150]}")
        
        page.close()
    
    # Check if kiro-cli got the token
    proc.kill()
    print("\n[*] kiro-cli process killed")
    print("[*] Done!")

if __name__ == '__main__':
    main()
