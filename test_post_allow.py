"""Capture ALL network requests after Allow click."""
import sys, os, time, string, random, uuid
from playwright.sync_api import sync_playwright
import boto3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_otp_v3 import extract_otp_gmail_v3

client = boto3.client('sso-oidc', region_name='us-east-1')
reg = client.register_client(clientName=f'kiro-{uuid.uuid4().hex[:8]}', clientType='public')
device = client.start_device_authorization(
    clientId=reg['clientId'],
    clientSecret=reg['clientSecret'],
    startUrl='https://view.awsapps.com/start'
)
user_code = device['userCode']
device_code = device['deviceCode']
print(f"[+] User code: {user_code}")

email = sys.argv[1] if len(sys.argv) > 1 else "testpy035@havenhaus.in"
name = sys.argv[2] if len(sys.argv) > 2 else "Test User"

password_chars = (random.choices(string.ascii_uppercase, k=4) + 
                  random.choices(string.ascii_lowercase, k=4) + 
                  random.choices(string.digits, k=4) + 
                  ['!', '@', '#', '$'])
random.shuffle(password_chars)
password = ''.join(password_chars)

all_requests = []

def on_request(request):
    all_requests.append({
        'url': request.url,
        'method': request.method,
        'time': time.time()
    })

def on_response(response):
    url = response.url
    # Capture token-related responses
    if any(k in url for k in ['token', 'credential', 'oidc', 'sso']):
        try:
            body = response.text()
            if body and len(body) > 5:
                print(f"[+] [{response.status}] {response.request.method} {url}")
                print(f"    Body: {body[:300]}")
        except Exception:
            pass

def dismiss_cookies_sync(page):
    for _ in range(10):
        for btn_text in ["Decline", "Dismiss", "Accept"]:
            try:
                btns = page.locator(f'button:has-text("{btn_text}")').all()
                for btn in btns:
                    if btn.is_visible(timeout=1000):
                        btn.click(timeout=2000)
                        time.sleep(0.5)
            except Exception:
                pass
        time.sleep(1)
        body = page.evaluate("document.body ? document.body.innerText : ''")
        if body and len(body) > 50 and 'cookie' not in body.lower()[:100]:
            break
    time.sleep(2)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=30000)
    context = browser.contexts[0]
    page = context.new_page()
    page.on("request", on_request)
    page.on("response", on_response)
    
    # Device page
    page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
              wait_until='domcontentloaded', timeout=30000)
    time.sleep(5)
    
    page.locator('button:has-text("Continue")').first.click(timeout=10000)
    print("[+] Device Continue clicked")
    time.sleep(8)
    dismiss_cookies_sync(page)
    
    # Email
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'email' in body.lower() or 'sign in' in body.lower():
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.wait_for(timeout=10000)
            inp.fill(email)
            inp.press('Enter')
            print("[+] Email submitted")
        except Exception as e:
            print(f"[!] Email: {e}")
        time.sleep(5)
    dismiss_cookies_sync(page)
    
    # Name
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'name' in body.lower():
        try:
            inp = page.locator('input:not([type="password"]):visible').first
            inp.fill(name)
            page.locator('button:has-text("Continue")').first.click(timeout=3000)
            print("[+] Name submitted")
        except Exception as e:
            print(f"[!] Name: {e}")
        time.sleep(5)
    dismiss_cookies_sync(page)
    
    # OTP
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'verify' in body.lower() or 'one-time' in body.lower() or ('code' in body.lower() and 'enter' in body.lower()):
        otp = extract_otp_gmail_v3(email)
        if otp:
            try:
                inp = page.locator('input:visible').first
                inp.fill(otp)
                inp.press('Enter')
                print(f"[+] OTP: {otp}")
            except Exception as e:
                print(f"[!] OTP: {e}")
            time.sleep(5)
    dismiss_cookies_sync(page)
    
    # Password
    body = page.evaluate("document.body ? document.body.innerText : ''")
    if 'password' in body.lower():
        try:
            inputs = page.locator('input[type="password"]:visible').all()
            if inputs:
                inputs[0].fill(password)
                if len(inputs) > 1:
                    inputs[1].fill(password)
                page.locator('button:has-text("Continue")').first.click(timeout=3000)
                print("[+] Password submitted")
        except Exception as e:
            print(f"[!] Password: {e}")
        time.sleep(5)
    dismiss_cookies_sync(page)
    
    # Allow
    body = page.evaluate("document.body ? document.body.innerText : ''")
    buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
    print(f"[+] Buttons: {buttons}")
    
    if 'Confirm and continue' in buttons:
        page.locator('button:has-text("Confirm and continue")').first.click(timeout=5000)
        time.sleep(8)
        dismiss_cookies_sync(page)
        body = page.evaluate("document.body ? document.body.innerText : ''")
        buttons = page.evaluate("Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t).join(' | ')")
        if 'Allow' in buttons:
            print("[*] Clicking Allow...")
            page.locator('button:has-text("Allow")').first.click(timeout=5000)
    elif 'Allow' in buttons:
        print("[*] Clicking Allow...")
        page.locator('button:has-text("Allow")').first.click(timeout=5000)
    
    # Wait longer and capture post-allow requests
    time.sleep(15)
    print(f"[+] Final URL: {page.url}")
    
    # Check IndexedDB
    print("\n[*] Checking IndexedDB...")
    idb_dbs = page.evaluate("""async () => {
        try {
            const dbs = await indexedDB.databases();
            return dbs.map(d => d.name);
        } catch(e) { return ['ERROR: ' + e.message]; }
    }""")
    print(f"[+] IndexedDB databases: {idb_dbs}")
    
    for db_name in idb_dbs:
        if 'ERROR' in str(db_name):
            continue
        try:
            idb_data = page.evaluate(f"""async () => {{
                try {{
                    const db = await new Promise((res, rej) => {{
                        const req = indexedDB.open('{db_name}');
                        req.onsuccess = () => res(req.result);
                        req.onerror = () => rej(req.error);
                    }});
                    const stores = Array.from(db.objectStoreNames);
                    const data = {{}};
                    for (const store of stores) {{
                        try {{
                            const tx = db.transaction(store, 'readonly');
                            const objStore = tx.objectStore(store);
                            const items = await new Promise((res, rej) => {{
                                const req = objStore.getAll();
                                req.onsuccess = () => res(req.result);
                                req.onerror = () => rej(req.error);
                            }});
                            data[store] = items.map(i => {{
                                if (typeof i === 'string') return i.substring(0, 100);
                                if (typeof i === 'object' && i !== null) {{
                                    const keys = Object.keys(i);
                                    const obj = {{}};
                                    for (const k of keys) {{
                                        const v = i[k];
                                        obj[k] = typeof v === 'string' ? v.substring(0, 80) : (typeof v === 'object' ? 'OBJECT' : v);
                                    }}
                                    return obj;
                                }}
                                return String(i).substring(0, 100);
                            }});
                        }} catch(e) {{ data[store] = ['ERROR: ' + e.message]; }}
                    }}
                    db.close();
                    return data;
                }} catch(e) {{ return {{error: e.message}}; }}
            }}""")
            print(f"[+] DB '{db_name}': {json.dumps(idb_data, indent=2)[:1000]}")
        except Exception as e:
            print(f"[!] DB '{db_name}' error: {e}")
    
    page.close()
    context.close()

# Print all requests
print(f"\n[+] Total requests: {len(all_requests)}")
# Focus on requests after Allow click (last 20)
for req in all_requests[-20:]:
    print(f"  [{req['method']}] {req['url']}")
