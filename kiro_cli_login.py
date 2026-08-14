"""
Kiro CLI Login with browser automation.
Starts kiro-cli login --use-device-flow, captures the user code,
automates the AWS auth in the existing browser, and captures the token.
"""
import sys, os, time, subprocess, re, json
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

EMAIL = 'ax3p0kzyk6@havenhaus.in'

def get_page_state(page):
    try:
        return page.evaluate("""() => {
            const body = (document.body?.innerText || '').toLowerCase();
            return {
                onName: body.includes('enter your name'),
                onOtp: body.includes('verify your email'),
                onAllow: body.includes('allow'),
                onErr: body.includes('err-837'),
                hash: window.location.hash,
                snippet: body.substring(0, 300)
            };
        }""")
    except Exception:
        return {'onName': False, 'onOtp': False, 'onAllow': False, 'onErr': False}

def main():
    # Start kiro-cli login
    print("[*] Starting kiro-cli login...")
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
            raw = stripped.split('Code:')[1].strip()
            code = raw
            break
        time.sleep(1)
    
    if not code:
        print("[!] No code received")
        proc.kill()
        return
    
    print(f"[*] User Code: {code}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        # Navigate to device auth page
        url = f'https://view.awsapps.com/start/#/device?user_code={code}'
        print(f"[*] Navigating to: {url}")
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(8.0)
        
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
        except Exception: pass
        time.sleep(10.0)
        
        state = get_page_state(page)
        print(f"[*] After device continue: hash={state.get('hash')}, snippet={state.get('snippet', '')[:100]}")
        
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
        page.keyboard.press('Enter')
        time.sleep(12.0)
        
        state = get_page_state(page)
        print(f"[*] After email: hash={state.get('hash')}, snippet={state.get('snippet', '')[:100]}")
        
        # Handle name page
        if state.get('onName'):
            print("[*] On name page - filling name and retrying...")
            # Try different names with retries
            names = ['John Smith', 'Test User', 'AWS User', 'Demo Account']
            success = False
            for name in names:
                page.evaluate(f"""() => {{
                    const inputs = document.querySelectorAll('input');
                    for (const inp of inputs) {{
                        const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                        if (!vis) continue;
                        const type = (inp.type || '').toLowerCase();
                        if (type === 'text') {{
                            inp.focus();
                            inp.value = '';
                            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            s.call(inp, '{name}');
                            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return true;
                        }}
                    }}
                    return false;
                }}""")
                time.sleep(1.0)
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
                time.sleep(10.0)
                
                state = get_page_state(page)
                print(f"[*] After name '{name}': onErr={state.get('onErr')}, onOtp={state.get('onOtp')}, onAllow={state.get('onAllow')}")
                
                if state.get('onOtp') or state.get('onAllow'):
                    success = True
                    break
            
            if not success:
                print("[!] All name attempts failed")
                page.close()
                proc.kill()
                return
        else:
            print("[!] Not on name page, unexpected state")
        
        # OTP
        if state.get('onOtp'):
            print("[*] Getting OTP...")
            otp_arrival = time.time()
            time.sleep(15.0)
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
                time.sleep(8.0)
                
                # Click Confirm
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
                time.sleep(8.0)
                
                state = get_page_state(page)
                print(f"[*] After OTP/Confirm: onAllow={state.get('onAllow')}, onErr={state.get('onErr')}")
                print(f"[*] Snippet: {state.get('snippet', '')[:200]}")
                
                if state.get('onAllow'):
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
                    time.sleep(15.0)
        
        # Final state
        time.sleep(5.0)
        state = get_page_state(page)
        print(f"[*] Final: hash={state.get('hash')}, onAllow={state.get('onAllow')}")
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] Final body: {body[:500]}")
        page.close()
    
    # Check kiro-cli output
    print("[*] Checking kiro-cli output...")
    proc.stdout.close()
    proc.wait(timeout=10)
    
    if proc.returncode == 0:
        print("[+] kiro-cli login succeeded!")
        # Try to read the secret store
        print("[*] Looking for kiro-cli secret store...")
        secret_paths = [
            '/home/ubuntu/.config/kiro-cli/secrets',
            '/home/ubuntu/.kiro-cli/secrets',
            '/home/ubuntu/.kiro/secrets',
            os.path.expanduser('~/.config/kiro-cli'),
        ]
        for sp in secret_paths:
            if os.path.exists(sp):
                print(f"  [+] Found: {sp}")
                for root, dirs, files in os.walk(sp):
                    for f in files:
                        fp = os.path.join(root, f)
                        print(f"    - {fp}")
    else:
        print(f"[!] kiro-cli exited with code {proc.returncode}")

if __name__ == '__main__':
    main()
