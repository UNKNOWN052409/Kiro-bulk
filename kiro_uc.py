#!/usr/bin/env python3
"""
Kiro AI Account Creator using undetected-chromedriver
Patches Chrome at binary level to avoid CDP/automation detection.
Uses SOCKS5 bridge for residential proxy.
"""

import uuid, secrets, hashlib, base64, time, random, re, json, sys
from urllib.parse import quote
import subprocess
import socket
from curl_cffi import requests as cffi_requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CALLBACK_PORT = 9997
SOCKS5_PORT = 10800
HTTP_PROXY_PORT = 8899
GMAIL_USER = 'anshika31618@gmail.com'
GMAIL_PASS = 'hlcv eobi tfwh terw'

FIRST_NAMES = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sophia', 'Mason', 'Isabella', 'William',
               'James', 'Charlotte', 'Benjamin', 'Lucas', 'Harper', 'Henry', 'Alexander', 'Sebastian', 'Jack', 'Owen']
LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Martinez', 'Wilson',
              'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Allen', 'King', 'Scott']

CHROME_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'


def create_cffi_session():
    # No proxy - direct connection for OIDC
    return cffi_requests.Session(
        impersonate='chrome124',
        timeout=60,
    )


def extract_otp():
    import imaplib, email as email_lib, email.utils
    from datetime import datetime, timezone
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select('inbox')
        # Search all Amazon emails (regardless of alias)
        status, messages = mail.search(None, '(FROM "amazon")')
        if status != 'OK' or not messages[0]:
            mail.logout()
            return None
        msg_ids = messages[0].split()
        for msg_id in reversed(msg_ids[-10:]):
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            if 'amazon' not in msg.get('From', '').lower():
                continue
            try:
                msg_date = email.utils.parsedate_to_datetime(msg.get('Date', ''))
                if msg_date.tzinfo:
                    age = (datetime.now(timezone.utc) - msg_date).total_seconds()
                    if age > 300:
                        continue
            except:
                pass
            otp = None
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() in ('text/plain', 'text/html'):
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        if 'html' in part.get_content_type():
                            body = re.sub(r'<[^>]+>', ' ', body)
                        m = re.search(r'\b(\d{6})\b', body)
                        if m:
                            otp = m.group(1)
                            break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                m = re.search(r'\b(\d{6})\b', body)
                if m:
                    otp = m.group(1)
            if otp:
                mail.logout()
                return otp
        mail.logout()
        return None
    except Exception as e:
        print(f"    [Gmail] Error: {e}")
        return None


def type_human(element, text, driver):
    """Type text with human-like delays"""
    element.click()
    time.sleep(random.uniform(0.3, 0.7))
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))


def create_account():
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    full_name = f'{first_name} {last_name}'
    random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
    # Use Gmail alias for testing (bypasses domain flagging)
    email_addr = f'anshika31618+kiro{random_suffix}@gmail.com'
    password = f'Kiro{random_suffix[:4]}!2026'
    
    account_info = {'email': email_addr, 'name': full_name, 'password': password, 'status': 'pending'}
    
    print(f"\n{'='*60}")
    print(f"Creating: {full_name} <{email_addr}>")
    print(f"{'='*60}\n")
    
    # Register OIDC client via curl_cffi
    print("[1] Registering OIDC client...")
    cffi_session = create_cffi_session()
    reg_data = {
        'clientName': f'kiro-{uuid.uuid4().hex[:8]}',
        'clientType': 'public',
        'scopes': ['codewhisperer:completions', 'codewhisperer:analysis', 'codewhisperer:conversations'],
        'grantTypes': ['authorization_code', 'refresh_token'],
        'redirectUris': [f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback'],
        'issuerUrl': 'https://view.awsapps.com/start'
    }
    reg_resp = cffi_session.post('https://oidc.us-east-1.amazonaws.com/client/register', json=reg_data)
    if reg_resp.status_code != 200:
        account_info['status'] = 'failed_register'
        cffi_session.close()
        return account_info
    client_id = reg_resp.json()['clientId']
    print(f"    Client ID: {client_id}")
    
    # PKCE
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    
    state = secrets.token_urlsafe(16)
    scopes = 'codewhisperer:completions codewhisperer:analysis codewhisperer:conversations'
    auth_url = (f'https://oidc.us-east-1.amazonaws.com/authorize?response_type=code'
                f'&client_id={client_id}'
                f'&redirect_uri={quote(f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback")}'
                f'&scopes={quote(scopes)}'
                f'&state={state}'
                f'&code_challenge={code_challenge}'
                f'&code_challenge_method=S256')
    
    # Launch undetected Chrome with SOCKS5 proxy
    print("[2] Starting undetected Chrome with SOCKS5 proxy...")
    options = uc.ChromeOptions()
    # NO proxy - direct connection test
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')
    options.add_argument(f'--user-agent={CHROME_UA}')
    
    driver = uc.Chrome(
        options=options,
        driver_executable_path='/home/ubuntu/kiro-gen/chromedriver/chromedriver-linux64/chromedriver',
        browser_executable_path='/usr/bin/chromium',
        headless=True,
        version_main=151,
    )
    
    try:
        # Execute stealth script
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                window.chrome = {runtime: {}};
            '''
        })
        
        print("[3] Navigating to authorize...")
        driver.get(auth_url)
        time.sleep(5)
        print(f"    Page URL: {driver.current_url[:100]}")
        
        # Email
        print("[4] Submitting email...")
        try:
            email_input = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="email"]'))
            )
            type_human(email_input, email_addr, driver)
            time.sleep(1)
            
            # Click Continue using JS
            driver.execute_script("""
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.textContent.trim() === 'Continue' && btn.offsetParent !== null) {
                        btn.click();
                        break;
                    }
                }
            """)
            print("    Email submitted (JS click)!")
            time.sleep(15)  # Longer wait
        except Exception as e:
            print(f"    [!] Email error: {e}")
            driver.save_screenshot('/home/ubuntu/kiro-gen/debug_email_uc.png')
            account_info['status'] = 'failed_email'
            driver.quit()
            return account_info
        
        # Name
        print("[5] Submitting name...")
        try:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//*[contains(text(), "Enter your name")]'))
            )
            print("    Name form detected!")
            
            name_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="text"]'))
            )
            type_human(name_input, full_name, driver)
            time.sleep(1)
            
            # Click Continue using JS
            driver.execute_script("""
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.textContent.trim() === 'Continue' && btn.offsetParent !== null) {
                        btn.click();
                        break;
                    }
                }
            """)
            print("    Name submitted (JS click)!")
            time.sleep(15)  # Longer wait
            
            # Check for error - also check current URL
            current_url = driver.current_url
            print(f"    After name submit URL: {current_url[:80]}")
            page_text = driver.page_source.lower()
            if 'err-837' in page_text:
                print("    [!] ERR-837 detected!")
                driver.save_screenshot('/home/ubuntu/kiro-gen/debug_tes_uc.png')
                account_info['status'] = 'failed_tes_name'
                driver.quit()
                return account_info
        except Exception as e:
            print(f"    [!] Name error: {e}")
            driver.save_screenshot('/home/ubuntu/kiro-gen/debug_name_uc.png')
            account_info['status'] = 'failed_name'
            driver.quit()
            return account_info
        
        # OTP
        print("[6] Handling OTP...")
        try:
            WebDriverWait(driver, 90).until(
                lambda d: any(kw in d.page_source.lower() for kw in ['one-time', 'verification code', 'enter the code'])
            )
            print("    OTP form detected!")
            
            otp_code = None
            for j in range(20):
                otp_code = extract_otp()
                if otp_code:
                    break
                time.sleep(3)
            
            if otp_code:
                print(f"    OTP: {otp_code}")
                otp_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="text"], input[inputmode="numeric"]')
                for inp in otp_inputs:
                    if inp.is_displayed():
                        inp.clear()
                        inp.send_keys(otp_code)
                        time.sleep(0.5)
                        try:
                            btn = driver.find_element(By.XPATH, '//button[contains(text(), "Continue")]')
                            btn.click()
                            print("    OTP submitted!")
                            break
                        except:
                            pass
            else:
                print("    [!] OTP not found")
                account_info['status'] = 'failed_otp'
                driver.quit()
                return account_info
        except Exception as e:
            print(f"    [!] OTP error: {e}")
            driver.save_screenshot('/home/ubuntu/kiro-gen/debug_otp_uc.png')
            account_info['status'] = 'failed_otp'
            driver.quit()
            return account_info
        
        # Password
        print("[7] Setting password...")
        try:
            WebDriverWait(driver, 30).until(
                lambda d: 'password' in d.page_source.lower() and ('create' in d.page_source.lower() or 'set' in d.page_source.lower())
            )
            print("    Password form detected!")
            
            pw_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
            visible_pw = [inp for inp in pw_inputs if inp.is_displayed()]
            if visible_pw:
                visible_pw[0].clear()
                visible_pw[0].send_keys(password)
                time.sleep(0.5)
                if len(visible_pw) >= 2:
                    visible_pw[1].clear()
                    visible_pw[1].send_keys(password)
                    time.sleep(0.5)
                
                try:
                    btn = driver.find_element(By.XPATH, '//button[contains(text(), "Create") or @type="submit"]')
                    btn.click()
                    print("    Password submitted!")
                except:
                    pass
        except Exception as e:
            print(f"    [!] Password error: {e}")
            driver.save_screenshot('/home/ubuntu/kiro-gen/debug_pw_uc.png')
            account_info['status'] = 'failed_password'
            driver.quit()
            return account_info
        
        # Wait for OAuth redirect
        print("[8] Waiting for OAuth redirect...")
        oauth_code = None
        for i in range(15):
            time.sleep(2)
            url = driver.current_url
            code_match = re.search(r'code=([A-Za-z0-9._~\-]+)', url)
            if code_match:
                oauth_code = code_match.group(1)
                break
        
        print(f"    Final URL: {driver.current_url[:100]}")
        driver.quit()
        
        if oauth_code:
            print(f"    OAuth code captured!")
            account_info['oauth_code'] = oauth_code
            account_info['code_verifier'] = code_verifier
            account_info['client_id'] = client_id
            
            # Exchange for token
            print("[9] Exchanging code for token...")
            token_resp = cffi_session.post('https://oidc.us-east-1.amazonaws.com/token', json={
                'grant_type': 'authorization_code',
                'client_id': client_id,
                'code': oauth_code,
                'redirect_uri': f'http://127.0.0.1:{CALLBACK_PORT}/oauth/callback',
                'code_verifier': code_verifier
            })
            if token_resp.status_code == 200:
                token_data = token_resp.json()
                account_info['access_token'] = token_data.get('access_token', '')
                account_info['refresh_token'] = token_data.get('refresh_token', '')
                account_info['id_token'] = token_data.get('id_token', '')
                account_info['status'] = 'success'
                print("    ✓ Token captured!")
            else:
                print(f"    [!] Token exchange failed: {token_resp.text[:200]}")
                account_info['status'] = 'partial'
        else:
            account_info['status'] = 'no_oauth_code'
    
    except Exception as e:
        print(f"    [!] Fatal: {e}")
        account_info['status'] = 'failed_exception'
        try:
            driver.quit()
        except:
            pass
    
    cffi_session.close()
    return account_info


if __name__ == '__main__':
    result = create_account()
    print(f"\n{'='*60}")
    print(f"Result: {json.dumps(result, indent=2)}")
    print(f"{'='*60}")
    
    with open('/home/ubuntu/kiro-gen/last_account.json', 'w') as f:
        json.dump(result, f, indent=2)
