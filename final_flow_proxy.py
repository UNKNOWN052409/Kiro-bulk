"""
FINAL FLOW with SOCKS5 Proxy (via relay):
- Launches local Chromium (non-headless via Xvfb) with SOCKS5 proxy
- Full AWS Builder ID auth: Email -> Name -> OTP -> Password -> Allow
- Token capture via OIDC polling
- Panel import
"""
import sys, os, time, uuid, threading, string, random
import boto3
from botocore.exceptions import ClientError
from playwright.sync_api import sync_playwright
from extract_otp_v3 import extract_otp_gmail_v3

def safe_eval(page, js, default=None):
    try:
        return page.evaluate(js)
    except Exception:
        return default

def get_state(page):
    body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''", '')
    return {
        'body': body or '',
        'onName': 'enter your name' in body,
        'onOtp': 'verify your email' in body or 'verification code' in body or 'verify your identity' in body,
        'onPasswordCreate': 'create your password' in body,
        'onAllow': 'allow' in body,
        'onErr': 'err-837' in body,
        'onRateLimit': 'retry in' in body and ('minute' in body or 'minutes' in body),
        'onGetStarted': 'get started' in body,
    }

def find_input(page, index=0):
    selectors = ['input:not([type="password"]):visible', 'input[type="email"]:visible', 'input[type="text"]:visible', 'input:visible']
    for sel in selectors:
        try:
            inp = page.locator(sel).nth(index)
            inp.wait_for(timeout=5000)
            if inp.is_visible():
                return inp
        except Exception:
            continue
    return None

def find_password_input(page, index=0):
    try:
        inp = page.locator('input[type="password"]:visible').nth(index)
        inp.wait_for(timeout=5000)
        if inp.is_visible():
            return inp
    except Exception:
        pass
    return None

def handle_cookies(page):
    body = safe_eval(page, "document.body ? document.body.innerText.toLowerCase() : ''")
    if body and ('cookie preferences' in body or 'essential cookies' in body):
        try:
            page.locator('button:has-text("Decline")').first.click(timeout=3000)
        except Exception:
            try:
                page.locator('button:has-text("Accept")').first.click(timeout=3000)
            except Exception:
                pass
        time.sleep(3.0)

def generate_password():
    chars = string.ascii_letters + string.digits
    password = ''.join(random.choice(chars) for _ in range(16))
    return password

def add_to_panel(refresh_token, email):
    import requests
    session = requests.Session()
    resp = session.post("https://ourproxy.sryze.cc/api/auth/login",
                       json={"password": "7894561230"}, timeout=10)
    if not resp.ok:
        print(f"  Panel login failed: {resp.status_code}")
        return False
    resp = session.post("https://ourproxy.sryze.cc/api/oauth/kiro/import",
                       json={
                           "refreshToken": refresh_token,
                           "region": "us-east-1",
                           "authMethod": "builder-id",
                           "startUrl": "https://view.awsapps.com/start",
                           "name": email
                       }, timeout=30)
    if not resp.ok:
        print(f"  Panel import failed: {resp.status_code} - {resp.text[:200]}")
        return False
    return True

def wait_for_state(page, states_to_check, max_wait=30, interval=1.0):
    for _ in range(int(max_wait / interval)):
        time.sleep(interval)
        state = get_state(page)
        for s in states_to_check:
            if state.get(s):
                return state
    return get_state(page)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 final_flow_proxy.py <email>")
        return

    email = sys.argv[1]
    name = email.split('@')[0]
    password = generate_password()
    print(f"[*] Processing: {email}")

    # Register OIDC client
    client = boto3.client('sso-oidc', region_name='us-east-1')
    reg = client.register_client(
        clientName=f'kiro-{uuid.uuid4().hex[:8]}',
        clientType='public'
    )
    device = client.start_device_authorization(
        clientId=reg['clientId'],
        clientSecret=reg['clientSecret'],
        startUrl='https://view.awsapps.com/start'
    )
    user_code = device['userCode']
    device_code = device['deviceCode']
    interval_sec = device['interval']
    expires_in = device['expiresIn']
    print(f"[*] User Code: {user_code}")

    token_received = [None]

    def poll_token():
        deadline = time.time() + expires_in + 300
        while time.time() < deadline and token_received[0] is None:
            time.sleep(interval_sec)
            try:
                resp = client.create_token(
                    clientId=reg['clientId'],
                    clientSecret=reg['clientSecret'],
                    grantType='urn:ietf:params:oauth:grant-type:device_code',
                    deviceCode=device_code
                )
                token_received[0] = resp.get('refreshToken')
                print("[+] TOKEN RECEIVED!")
                return
            except ClientError as e:
                err = e.response['Error']['Code']
                if err in ('AuthorizationPendingException', 'SlowDownException'):
                    continue
                else:
                    print(f"[!] Token poll: {err}")
                    return

    poll_thread = threading.Thread(target=poll_token, daemon=True)
    poll_thread.start()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--proxy-server=socks5://127.0.0.1:10080',
                '--proxy-bypass-list=<-loopback>'
            ]
        )
        context = browser.new_context()
        page = context.new_page()

        # Navigate to device page
        try:
            page.goto(f'https://view.awsapps.com/start/#/device?user_code={user_code}',
                      wait_until='commit', timeout=60000)
        except Exception as e:
            print(f"Goto: {e}")

        # Wait for content
        for i in range(30):
            time.sleep(1.0)
            body = safe_eval(page, "document.body ? document.body.innerText : ''", '')
            if body and len(body) > 30 and 'forbidden' not in body.lower():
                break

        handle_cookies(page)

        # Click Continue on device page
        try:
            page.locator('button:has-text("Continue")').first.click(timeout=5000)
            print("[+] Device Continue clicked")
        except Exception:
            print("[!] Device Continue failed")

        # Wait for email page
        state = wait_for_state(page, ['onGetStarted'], max_wait=20)
        if not state['onGetStarted']:
            print(f"[!] Expected Get Started page, got: {state['body'][:100]}")

        # Fill email
        inp = find_input(page)
        if not inp:
            print("[!] No email input found")
            page.close(); context.close(); browser.close()
            poll_thread.join(timeout=5)
            return False

        inp.click()
        inp.press('Control+a')
        inp.press('Backspace')
        inp.fill(email)
        inp.press('Enter')
        print("[+] Email submitted")

        # Wait for next state
        state = wait_for_state(page, ['onName', 'onOtp', 'onErr', 'onRateLimit'], max_wait=30)
        print(f"After email: onName={state['onName']}, onOtp={state['onOtp']}, err={state['onErr']}")

        if state['onRateLimit']:
            print("[!] Rate limited - aborting")
            page.close(); context.close(); browser.close()
            poll_thread.join(timeout=5)
            return False

        # Name page
        if state['onName']:
            inp = find_input(page)
            if inp:
                inp.click()
                inp.type(name.title(), delay=100)
                time.sleep(1.0)
                try:
                    page.locator('button:has-text("Continue")').first.click(timeout=5000)
                    print("[+] Name submitted")
                except Exception:
                    pass

                state = wait_for_state(page, ['onOtp', 'onErr', 'onRateLimit'], max_wait=30)

                # Retry ERR-837 up to 3 times
                max_retries = 3
                for retry_num in range(max_retries):
                    if state['onOtp']:
                        break
                    if state['onErr'] or state['onRateLimit']:
                        print(f"[!] ERR-837/rateLimit - retry {retry_num+1}/{max_retries}, waiting 180s...")
                        time.sleep(180)
                        inp = find_input(page)
                        if inp:
                            inp.click()
                            inp.type(name.title(), delay=100)
                            time.sleep(1.0)
                            try:
                                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                                print(f"[+] Name submitted (retry {retry_num+1})")
                            except Exception:
                                pass
                        state = wait_for_state(page, ['onOtp', 'onErr', 'onRateLimit'], max_wait=30)
                    else:
                        break

                if state['onErr'] or state['onRateLimit']:
                    print(f"[!] Failed: err={state['onErr']}, rateLimit={state['onRateLimit']}")
                    page.close(); context.close(); browser.close()
                    poll_thread.join(timeout=5)
                    return False

        # OTP page
        if state['onOtp']:
            print("[*] Waiting for OTP...")
            otp_arrival = time.time()
            otp = None

            # Try immediately (might already be there)
            try:
                otp = extract_otp_gmail_v3(email, after_timestamp=otp_arrival - 300)
            except Exception as e:
                print(f"[!] OTP extract error: {e}")

            # Poll for OTP
            if not otp:
                for _ in range(30):
                    time.sleep(10)
                    try:
                        otp = extract_otp_gmail_v3(email, after_timestamp=otp_arrival - 300)
                        if otp:
                            break
                    except Exception:
                        pass

            if otp:
                print(f"[+] OTP: {otp}")
                inp = find_input(page)
                if inp:
                    inp.click()
                    inp.fill(otp)
                    inp.press('Enter')
                    print("[+] OTP submitted")
                    time.sleep(8.0)

                try:
                    page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                    print("[+] Confirm clicked")
                except Exception:
                    pass

                # Wait for password creation page
                state = wait_for_state(page, ['onPasswordCreate', 'onAllow', 'onErr'], max_wait=60)
                print(f"After confirm: onPasswordCreate={state['onPasswordCreate']}, onAllow={state['onAllow']}")
            else:
                print("[!] No OTP received - aborting")
                page.close(); context.close(); browser.close()
                poll_thread.join(timeout=5)
                return False

        # Password creation page
        if state['onPasswordCreate']:
            print("[*] Creating password...")
            pass_inputs = page.locator('input[type="password"]:visible')
            count = pass_inputs.count()
            print(f"  Found {count} password inputs")

            pass_inputs.nth(0).click()
            pass_inputs.nth(0).fill(password)
            print(f"[+] Password filled: {len(password)} chars")
            time.sleep(3.0)

            # Wait for confirm field
            second_field = None
            for _ in range(20):
                time.sleep(1.0)
                pass_inputs = page.locator('input[type="password"]:visible')
                cnt = pass_inputs.count()
                if cnt > 1:
                    second_field = pass_inputs.nth(1)
                    print(f"[+] Second password field appeared (total: {cnt})")
                    break

            if second_field:
                second_field.click()
                second_field.fill(password)
                print("[+] Confirm password filled")
                time.sleep(2.0)
                second_field.press('Enter')
                print("[+] Enter pressed in confirm field")
            else:
                print(f"[!] Second field never appeared (count: {pass_inputs.count()})")
                pass_inputs.nth(0).press('Enter')

            state = wait_for_state(page, ['onAllow', 'onPasswordCreate', 'onErr'], max_wait=60)
            print(f"After password: onAllow={state['onAllow']}, onPasswordCreate={state['onPasswordCreate']}")

            if not state['onAllow']:
                print("[*] Trying Continue button...")
                try:
                    page.locator('button:has-text("Continue")').first.click(timeout=5000)
                    time.sleep(5.0)
                except Exception:
                    pass
                state = wait_for_state(page, ['onAllow', 'onPasswordCreate', 'onErr'], max_wait=30)
                print(f"After button click: onAllow={state['onAllow']}")

        # Allow page
        if state['onAllow']:
            print("[*] Clicking Allow...")
            try:
                page.locator('button:has-text("Allow")').first.click(timeout=5000)
                print("[+] Allow clicked - AUTH COMPLETE!")
                time.sleep(10.0)
            except Exception:
                print("[!] Allow click failed")
        else:
            print(f"[!] Expected Allow page but got: {state['body'][:150]}")

        page.close()
        context.close()
        browser.close()

    # Wait for token
    print("[*] Waiting for token...")
    poll_thread.join(timeout=180)
    if not token_received[0]:
        time.sleep(10)
    if not token_received[0]:
        time.sleep(10)
    if not token_received[0]:
        time.sleep(10)

    if token_received[0]:
        print("[+] Token captured!")
        if add_to_panel(token_received[0], email):
            print(f"[+] SUCCESS: {email} added to panel!")
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kiro_accounts.csv'), 'a') as f:
                f.write(f"{email},{time.strftime('%Y-%m-%d %H:%M:%S')},success,proxy\n")
            return True
        else:
            print("[!] Panel import failed")
            return False
    else:
        print("[!] Token not received")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
