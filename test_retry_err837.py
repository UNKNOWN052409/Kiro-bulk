"""Test retrying after ERR-837 with a realistic name."""
import sys, os, time, subprocess, re
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_add_ui import extract_otp_gmail

EMAIL = 'ax3p0kzyk6@havenhaus.in'

def get_page_state(page):
    return page.evaluate("""() => {
        const body = (document.body?.innerText || '').toLowerCase();
        return {
            onName: body.includes('enter your name'),
            onOtp: body.includes('verify your email'),
            onAllow: body.includes('allow'),
            onErr: body.includes('err-837'),
            url: window.location.href,
            hash: window.location.hash,
            snippet: body.substring(0, 300)
        };
    }""")

def main():
    proc = subprocess.Popen(
        ['kiro-cli', 'login', '--use-device-flow', '--license', 'free'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    code = None
    for i in range(30):
        line = proc.stdout.readline()
        if not line: break
        if 'Code:' in line:
            raw = line.strip().split('Code:')[1].strip()
            code = re.sub(r'\x1b\[[0-9;]*m', '', raw).strip()
            break
        time.sleep(1)
    
    if not code:
        print("[!] No code"); return
    print(f"[*] Code: {code}")
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
        context = browser.contexts[0]
        page = context.new_page()
        
        url = f'https://view.awsapps.com/start/#/device?user_code={code}'
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5.0)
        
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
        time.sleep(8.0)
        
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
        
        page_info = get_page_state(page)
        print(f"[*] After email: hash={page_info['hash']}, snippet={page_info['snippet'][:100]}")
        
        # Try up to 3 times with different names
        for attempt in range(3):
            if not page_info.get('onName'):
                break
                
            names = ['John Smith', 'Test User', 'AWS User']
            name = names[attempt % len(names)]
            print(f"[*] Attempt {attempt+1}: name='{name}'")
            
            # Fill name
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
            
            # Click Continue
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
            
            page_info = get_page_state(page)
            print(f"[*] After attempt {attempt+1}: hash={page_info['hash']}, err={page_info.get('onErr')}, onOtp={page_info.get('onOtp')}")
            print(f"[*] Snippet: {page_info['snippet'][:200]}")
            
            if page_info.get('onOtp') or page_info.get('onAllow'):
                break  # Success!
        
        if page_info.get('onOtp'):
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
                
                page_info3 = get_page_state(page)
                print(f"[*] After OTP: onAllow={page_info3.get('onAllow')}, err={page_info3.get('onErr')}")
                print(f"[*] Snippet: {page_info3['snippet'][:300]}")
                
                if page_info3.get('onAllow'):
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
                    time.sleep(12.0)
        
        # Final
        time.sleep(5.0)
        print(f"[*] Final hash: {page.evaluate('window.location.hash')}")
        body = page.evaluate("document.body.innerText").lower()
        print(f"[*] Final body: {body[:500]}")
        page.close()
        proc.kill()

if __name__ == '__main__':
    main()
