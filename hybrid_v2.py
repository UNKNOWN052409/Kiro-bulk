"""
Kiro AI Account Creator - Hybrid V2
- Browser WITHOUT proxy for OIDC → signin.aws → email submission
- After email submit, redirect to profile.aws.amazon.com
- Intercept ALL profile.aws.amazon.com requests via page.route() and replay through proxy
- This ensures the SPA loads fast (datacenter) but API calls use residential IP
"""

import uuid, secrets, hashlib, base64, requests, json, time, socket, threading, http.server, random
from urllib.parse import quote, urlparse
from playwright.sync_api import sync_playwright

# Config
REGION = 'us-east-1'
OIDC_BASE = f'https://oidc.{REGION}.amazonaws.com'
ISSUER_URL = 'https://view.awsapps.com/start'
GRANT_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"]
CALLBACK_PORT = 9997
DIRECTORY_ID = 'd-9067642ac7'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

# ProxyRise config
PROXYRISE_API_KEY = 'pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1'
PROXY_SESSION_ID = str(uuid.uuid4().int % (10**9))

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'Mia', 'James', 'Charlotte', 'Benjamin', 'Amelia', 'Lucas', 'Harper', 'Henry', 'Evelyn', 'Alexander',
               'Sebastian', 'Jack', 'Owen', 'Theodore', 'Aria', 'Scarlett', 'Victoria', 'Madison', 'Luna', 'Grace']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
              'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson',
              'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker', 'Young', 'Allen', 'King', 'Wright', 'Scott']


def replay_post_through_proxy(url, headers, body):
    """Replay a POST request through SOCKS5 residential proxy using curl_cffi."""
    from curl_cffi import requests as cffi_requests
    
    proxy_url = f"socks5h://res-us-sid-{PROXY_SESSION_ID}:{PROXYRISE_API_KEY}@gw.proxyrise.com:443"
    
    resp = cffi_requests.post(
        url,
        headers=headers,
        data=body.encode('utf-8') if isinstance(body, str) else body,
        proxy=proxy_url,
        impersonate='chrome131',
        timeout=30
    )
    
    return resp.status_code, dict(resp.headers), resp.text


def extract_otp():
    import imaplib, email as email_lib, re
    
    email_user = 'anshika31618@gmail.com'
    email_pass = 'hlcv eobi tfwh terw'
    
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_user, email_pass)
        mail.select('inbox')
        status, messages = mail.search(None, '(FROM "amazon.com" OR FROM "no-reply@amazon.com")')
        if status != 'OK' or not messages[0]:
            mail.logout()
            return None
        
        msg_ids = messages[0].split()
        for msg_id in reversed(msg_ids[-5:]):
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            from_addr = msg.get('From', '')
            if 'amazon' not in from_addr.lower():
                continue
            otp = None
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct in ('text/plain', 'text/html'):
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        if ct == 'text/html':
                            body = re.sub(r'<[^>]+>', ' ', body)
                        match = re.search(r'\b(\d{6})\b', body)
                        if match:
                            otp = match.group(1)
                            break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                match = re.search(r'\b(\d{6})\b', body)
                if match:
                    otp = match.group(1)
            if otp:
                mail.logout()
                return otp
        mail.logout()
        return None
    except Exception as e:
        print(f"    [!] Gmail error: {e}")
        return None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    captured_code = None
    captured_state = None
    
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        CallbackHandler.captured_code = params.get('code', [None])[0]
        CallbackHandler.captured_state = params.get('state', [None])[0]
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>OK</h1></body></html>')
    
    def log_message(self, format, *args):
        pass


def main():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    email = f'{random_suffix}@havenhaus.in'
    password = f'Kiro{random_suffix[:4]}!2026'
    
    print(f"Creating: {full_name} <{email}>")
    print(f"Password: {password}")
    print(f"Proxy session: {PROXY_SESSION_ID}")
    print()
    
    # Register OIDC client
    print("[1] Registering OIDC client...")
    reg_payload = {
        "clientName": f"kiro-{uuid.uuid4().hex[:8]}",
        "clientType": "public",
        "scopes": GRANT_SCOPES,
        "grantTypes": ["authorization_code", "refresh_token"],
        "redirectUris": [f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"],
        "issuerUrl": ISSUER_URL
    }
    reg_resp = requests.post(f'{OIDC_BASE}/client/register', json=reg_payload, timeout=10)
    client_id = reg_resp.json()['clientId']
    
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_urlsafe(16)
    redirect_uri = f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'
    auth_url = (f'{OIDC_BASE}/authorize?response_type=code&client_id={client_id}'
                f'&redirect_uri={quote(redirect_uri)}&scopes={quote(" ".join(GRANT_SCOPES))}'
                f'&state={state}&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    # Start callback server
    CallbackHandler.captured_code = None
    callback_server = http.server.HTTPServer(('127.0.0.1', CALLBACK_PORT), CallbackHandler)
    callback_server.daemon_threads = True
    threading.Thread(target=callback_server.serve_forever, daemon=True).start()
    
    print("[2] Launching browser (NO proxy for fast SPA loading)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=UA,
            locale='en-US',
        )
        page = context.new_page()
        page.set_default_timeout(60000)
        page.set_default_navigation_timeout(60000)
        
        # Track profile.aws.amazon.com API responses
        profile_api_responses = []
        def on_response(response):
            if 'profile.aws.amazon.com/api' in response.url:
                try:
                    body = response.json()
                    step = body.get('stepId', '')
                    error = body.get('message', {}).get('errorCode', '')
                    wsh = body.get('workflowStateHandle', '')
                    profile_api_responses.append({'step': step, 'error': error, 'wsh': wsh})
                    print(f"    [API] step={step}, err={error}")
                except:
                    pass
        
        page.on('response', on_response)
        
        # Navigate to OIDC authorize
        print("[3] Navigating to OIDC authorize...")
        page.goto(auth_url, wait_until='domcontentloaded', timeout=60000)
        time.sleep(3)
        
        # Wait for email form
        print("[4] Waiting for email form...")
        for i in range(20):
            time.sleep(2)
            try:
                body = page.evaluate('document.body.innerText')
                if 'email' in body.lower() and 'continue' in body.lower():
                    print(f"    Form ready at {i*2}s")
                    break
            except:
                pass
        
        # Fill email
        print("[5] Filling email...")
        try:
            email_input = page.locator('input[type="email"]').first
            email_input.fill(email)
            time.sleep(0.5)
            continue_btn = page.locator('button:has-text("Continue")').first
            continue_btn.click()
            print("    Email submitted!")
        except Exception as e:
            print(f"    Email error: {e}")
            # Try alternative
            try:
                inputs = page.evaluate("() => document.querySelectorAll('input').length")
                print(f"    Input count: {inputs}")
                # Try filling the first visible input
                page.evaluate(f"""
                    () => {{
                        const inputs = document.querySelectorAll('input');
                        for (const input of inputs) {{
                            if (input.type === 'email' || input.placeholder?.includes('Email')) {{
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                setter.call(input, '{email}');
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                return true;
                            }}
                        }}
                        return false;
                    }}
                """)
                # Click continue
                page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            if (btn.textContent.trim() === 'Continue') {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                print("    Email submitted (alternative method)!")
            except Exception as e2:
                print(f"    Alternative email error: {e2}")
        
        # Wait for redirect to profile.aws.amazon.com
        print("[6] Waiting for profile.aws.amazon.com redirect...")
        for i in range(20):
            time.sleep(2)
            url = page.url
            if 'profile.aws.amazon.com' in url:
                print(f"    Redirected to profile at {i*2}s!")
                break
            elif i >= 19:
                print(f"    Still on: {url[:60]}")
        
        # Now intercept profile.aws.amazon.com API calls
        print("[7] Setting up profile.aws.amazon.com proxy interception...")
        
        # Track intercepted requests
        intercepted_count = [0]
        
        async def handle_route(route):
            """Intercept profile.aws.amazon.com API calls and replay through proxy."""
            request = route.request
            
            if 'profile.aws.amazon.com' in request.url and request.method == 'POST':
                intercepted_count[0] += 1
                url = request.url
                headers = {k: v for k, v in request.headers.items() 
                          if k.lower() not in ('content-length', 'host')}
                
                print(f"    [PROXY] Intercepting POST to {url}")
                
                try:
                    body = request.post_data or ''
                    status, resp_headers, resp_body = replay_post_through_proxy(url, headers, body)
                    
                    print(f"    [PROXY] Response: {status}")
                    print(f"    [PROXY] Body: {resp_body[:150]}")
                    
                    route.fulfill(
                        status=status,
                        headers={k: v for k, v in resp_headers.items()},
                        body=resp_body
                    )
                except Exception as e:
                    print(f"    [PROXY] Error: {e}")
                    route.fulfill(status=500, body=json.dumps({"error": str(e)}))
            else:
                route.continue_()
        
        # Use sync API for route handling
        def sync_handle_route(route):
            request = route.request
            if 'profile.aws.amazon.com' in request.url and request.method == 'POST':
                intercepted_count[0] += 1
                url = request.url
                headers = {k: v for k, v in request.headers.items() 
                          if k.lower() not in ('content-length', 'host')}
                
                print(f"    [PROXY] Intercepting POST to {url}")
                
                try:
                    body = request.post_data or ''
                    status, resp_headers, resp_body = replay_post_through_proxy(url, headers, body)
                    
                    print(f"    [PROXY] Response: {status}")
                    if 'BLOCKED' in resp_body or 'ERR-837' in resp_body:
                        print(f"    [PROXY] TES BLOCKED! Body: {resp_body[:200]}")
                    
                    route.fulfill(
                        status=status,
                        headers={k: v for k, v in resp_headers.items() if k.lower() not in ('transfer-encoding',)},
                        body=resp_body
                    )
                except Exception as e:
                    print(f"    [PROXY] Error: {e}")
                    route.continue_()
            else:
                route.continue_()
        
        page.route('**/*', sync_handle_route)
        print("    Route handler registered!")
        
        # Wait for the name page to load
        print("[8] Waiting for name page...")
        time.sleep(5)
        
        # Dismiss cookie dialog
        try:
            accept_btn = page.locator('button:has-text("Accept")').first
            if accept_btn.is_visible(timeout=3000):
                accept_btn.click()
                time.sleep(1)
                print("    Cookie dismissed")
        except:
            pass
        
        # Check current state
        try:
            body = page.evaluate('document.body.innerText')
            url = page.url
            print(f"    URL: {url[:80]}")
            print(f"    Body: {body[:100]}")
        except Exception as e:
            print(f"    State check error: {e}")
        
        # Try to fill name
        print("[9] Attempting to fill name...")
        try:
            # Find the name input
            name_result = page.evaluate("""
                () => {
                    const inputs = document.querySelectorAll('input');
                    const results = [];
                    for (const input of inputs) {
                        results.push({
                            type: input.type,
                            name: input.name,
                            placeholder: input.placeholder,
                            visible: input.offsetParent !== null
                        });
                    }
                    return results;
                }
            """)
            print(f"    Inputs: {name_result}")
            
            # Try to fill name
            name_filled = page.evaluate(f"""
                () => {{
                    const inputs = document.querySelectorAll('input');
                    for (const input of inputs) {{
                        if ((input.type === 'text' || !input.type) && 
                            (input.placeholder?.toLowerCase().includes('name') || 
                             input.name?.toLowerCase().includes('name') ||
                             input.id?.toLowerCase().includes('name'))) {{
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            setter.call(input, '{full_name}');
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            return true;
                        }}
                    }}
                    return false;
                }}
            """)
            
            if name_filled:
                print(f"    Name filled via JS: {full_name}")
                time.sleep(0.5)
                
                # Click Continue
                clicked = page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            if (btn.textContent.trim().toLowerCase() === 'continue') {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                print(f"    Continue clicked: {clicked}")
            else:
                # Try locator approach
                try:
                    name_input = page.locator('input[type="text"]').first
                    name_input.wait_for(timeout=5000)
                    name_input.fill(full_name)
                    time.sleep(0.5)
                    page.locator('button:has-text("Continue")').first.click()
                    print(f"    Name filled via locator: {full_name}")
                except Exception as e:
                    print(f"    Name fill error: {e}")
                    
        except Exception as e:
            print(f"    Name detection error: {e}")
        
        # Wait for OTP page
        print("[10] Waiting for OTP page...")
        time.sleep(3)
        
        # Check state
        try:
            body = page.evaluate('document.body.innerText')
            print(f"    Body: {body[:100]}")
        except:
            pass
        
        # Wait for OTP API call
        otp_detected = False
        for i in range(30):
            time.sleep(2)
            try:
                body = page.evaluate('document.body.innerText')
                if 'code' in body.lower() or 'otp' in body.lower() or 'verification' in body.lower():
                    print(f"    OTP page at {i*2}s!")
                    otp_detected = True
                    break
                elif 'err-837' in body.lower():
                    print(f"    [{i*2}s] ERR-837 on page!")
                    break
            except:
                pass
        
        if otp_detected:
            # Get OTP from Gmail
            print("[11] Fetching OTP from Gmail...")
            otp = None
            for attempt in range(5):
                otp = extract_otp()
                if otp:
                    break
                time.sleep(3)
            
            if otp:
                print(f"    OTP: {otp}")
                # Fill OTP
                try:
                    otp_inputs = page.evaluate(f"""
                        () => {{
                            const inputs = document.querySelectorAll('input');
                            let count = 0;
                            for (const input of inputs) {{
                                if (input.type === 'text' || input.type === 'number' || !input.type) {{
                                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    setter.call(input, '{otp}');
                                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    count++;
                                    if (count >= 1) break;
                                }}
                            }}
                            return count;
                        }}
                    """)
                    print(f"    OTP filled: {otp} ({otp_inputs} inputs)")
                    
                    # Click Continue
                    page.evaluate("""
                        () => {
                            const buttons = document.querySelectorAll('button');
                            for (const btn of buttons) {
                                if (btn.textContent.trim().toLowerCase() === 'continue') {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    print("    OTP submitted!")
                    
                    # Wait for password page
                    print("[12] Waiting for password page...")
                    time.sleep(3)
                    
                    # Set password
                    try:
                        pw_result = page.evaluate(f"""
                            () => {{
                                const inputs = document.querySelectorAll('input[type="password"]');
                                if (inputs.length >= 1) {{
                                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    setter.call(inputs[0], '{password}');
                                    inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    if (inputs.length >= 2) {{
                                        setter.call(inputs[1], '{password}');
                                        inputs[1].dispatchEvent(new Event('input', {{ bubbles: true }}));
                                        inputs[1].dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    }}
                                    return true;
                                }}
                                return false;
                            }}
                        """)
                        if pw_result:
                            print(f"    Password set: {password}")
                            time.sleep(0.5)
                            
                            # Click Continue
                            page.evaluate("""
                                () => {
                                    const buttons = document.querySelectorAll('button');
                                    for (const btn of buttons) {
                                        if (btn.textContent.trim().toLowerCase() === 'continue' || 
                                            btn.textContent.trim().toLowerCase() === 'create account') {
                                            btn.click();
                                            return true;
                                        }
                                    }
                                    return false;
                                }
                            """)
                            print("    Password submitted!")
                            
                            # Wait for redirect
                            print("[13] Waiting for token redirect...")
                            time.sleep(5)
                            final_url = page.url
                            print(f"    Final URL: {final_url}")
                            if 'code=' in final_url:
                                from urllib.parse import parse_qs
                                parsed = urlparse(final_url)
                                params = parse_qs(parsed.query)
                                code = params.get('code', [None])[0]
                                print(f"    Auth code: {code}")
                            else:
                                print("    No code in URL, checking callback server...")
                                time.sleep(2)
                                if CallbackHandler.captured_code:
                                    print(f"    Auth code from callback: {CallbackHandler.captured_code}")
                        else:
                            print("    Could not set password")
                    except Exception as e:
                        print(f"    Password error: {e}")
                except Exception as e:
                    print(f"    OTP submission error: {e}")
            else:
                print("    Could not get OTP!")
        
        # Final state
        print("\n[FINAL]")
        try:
            body = page.evaluate('document.body.innerText')
            url = page.url
            print(f"    URL: {url}")
            print(f"    Body: {body[:200]}")
        except:
            pass
        
        try:
            page.screenshot(path='/home/ubuntu/kiro-gen/hybrid_v2_final.png', timeout=5000)
        except:
            pass
        
        browser.close()
    
    callback_server.shutdown()
    
    # Save result
    result = {
        'email': email,
        'password': password,
        'name': full_name,
        'proxy_session': PROXY_SESSION_ID,
        'intercepted_requests': intercepted_count[0],
        'api_responses': profile_api_responses,
    }
    with open('/home/ubuntu/kiro-gen/last_result.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\nResult saved. Intercepted {intercepted_count[0]} requests through proxy.")


if __name__ == '__main__':
    main()
