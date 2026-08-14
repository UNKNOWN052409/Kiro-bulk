#!/usr/bin/env python3
"""Test if we can skip the name page by not filling it."""
import sys
import os
import time
import subprocess
import re
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

EMAIL = 'ax3p0kzyk6@havenhaus.in'

def main():
    # Start kiro-cli login
    proc = subprocess.Popen(
        ['kiro-cli', 'login', '--use-device-flow', '--license', 'free'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    code = None
    for i in range(30):
        line = proc.stdout.readline()
        if not line:
            break
        if 'Code:' in line:
            raw = line.strip().split('Code:')[1].strip()
            code = re.sub(r'\x1b\[[0-9;]*m', '', raw).strip()
            break
        time.sleep(1)
    
    if not code:
        print("[!] No code")
        return
    
    print(f"[*] Code: {code}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        # Navigate
        url = f'https://view.awsapps.com/start/#/device?user_code={code}'
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3.0)
        
        # Click Continue on device page
        try:
            page.evaluate("""() => {
                const btns = document.querySelectorAll('button, a');
                for (const b of btns) {
                    const vis = b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled;
                    if (!vis) continue;
                    const t = (b.textContent || '').trim().toLowerCase();
                    if (t.includes('continue')) { b.click(); return true; }
                }
                return false;
            }""")
        except Exception:
            pass
        time.sleep(8.0)  # Wait for navigation to complete
        
        # Fill email and submit
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
        page.keyboard.press('Enter')
        time.sleep(8.0)
        
        # Check what page we're on
        page_info2 = None
        for attempt in range(5):
            try:
                page_info = page.evaluate("""() => {
                    const body = (document.body?.innerText || '').toLowerCase();
                    return {
                        onName: body.includes('enter your name'),
                        onOtp: body.includes('verify your email'),
                        onPassword: body.includes('password'),
                        onConfirm: body.includes('confirm'),
                        onAllow: body.includes('allow'),
                        url: window.location.href,
                        snippet: body.substring(0, 300)
                    };
                }""")
                print(f"[*] Page info: {page_info}")
                break
            except Exception:
                time.sleep(3.0)
        else:
            print("[!] Could not read page state")
            page.close()
            proc.kill()
            return
        
        # If on name page, try clicking Continue WITHOUT filling name
        if page_info['onName']:
            print("[*] On name page - trying Continue without filling name...")
            try:
                page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const vis = b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled;
                        if (!vis) continue;
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (t.includes('continue')) { b.click(); return true; }
                    }
                    return false;
                }""")
            except Exception:
                pass
            time.sleep(10.0)
            
            # Check again
            try:
                page_info2 = page.evaluate("""() => {
                    const body = (document.body?.innerText || '').toLowerCase();
                    return {
                        onName: body.includes('enter your name'),
                        onOtp: body.includes('verify your email'),
                        onConfirm: body.includes('confirm'),
                        url: window.location.href,
                        snippet: body.substring(0, 300)
                    };
                }""")
                print(f"[*] After Continue (no name): {page_info2}")
            except Exception:
                page_info2 = {'onOtp': False}
        else:
            page_info2 = {'onOtp': False}
        
        # If on OTP page, submit OTP
        if page_info.get('onOtp') or page_info2.get('onOtp'):
            print("[*] OTP page - getting fresh OTP...")
            otp_arrival = time.time()
            time.sleep(20.0)
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
                time.sleep(10.0)
                
                # Check for confirm
                page_info3 = page.evaluate("""() => {
                    const body = (document.body?.innerText || '').toLowerCase();
                    return {
                        onConfirm: body.includes('confirm'),
                        onAllow: body.includes('allow'),
                        url: window.location.href,
                        snippet: body.substring(0, 200)
                    };
                }""")
                print(f"[*] After OTP: {page_info3}")
                
                # Click Confirm
                if page_info3.get('onConfirm'):
                    page.evaluate("""() => {
                        const btns = document.querySelectorAll('button');
                        for (const b of btns) {
                            const vis = b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled;
                            if (!vis) continue;
                            const t = (b.textContent || '').trim().toLowerCase();
                            if (t.includes('confirm')) { b.click(); return true; }
                        }
                        return false;
                    }""")
                    time.sleep(10.0)
                
                # Click Allow
                page_info4 = page.evaluate("""() => {
                    const body = (document.body?.innerText || '').toLowerCase();
                    return {
                        onAllow: body.includes('allow'),
                        url: window.location.href,
                        snippet: body.substring(0, 200)
                    };
                }""")
                print(f"[*] After Confirm: {page_info4}")
                
                if page_info4.get('onAllow'):
                    page.evaluate("""() => {
                        const btns = document.querySelectorAll('button');
                        for (const b of btns) {
                            const vis = b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled;
                            if (!vis) continue;
                            const t = (b.textContent || '').trim().toLowerCase();
                            if (t.includes('allow')) { b.click(); return true; }
                        }
                        return false;
                    }""")
                    time.sleep(10.0)
        
        # Final state
        time.sleep(5.0)
        final_url = page.url
        print(f"[*] Final URL: {final_url}")
        
        page.close()
    
    proc.kill()
    print("[*] Done!")

if __name__ == '__main__':
    main()
