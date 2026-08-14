"""
Panel Add Account via UI Modal Device Auth Flow
================================================

This module provides a working implementation of adding Kiro AI accounts
to the 9Router panel using the UI-based device auth flow.

Flow:
1. Panel login
2. Navigate to /dashboard/providers/kiro
3. Click "Add" button
4. Click "AWS Builder ID" in modal
5. Extract Login URL from modal
6. Navigate to AWS login URL
7. Sign in (email -> password -> OTP -> Confirm -> Allow)
8. Account auto-added to panel

Dependencies:
- Playwright
- imaplib (Gmail OTP extraction)
"""

import re, time, random, imaplib, email
from typing import Optional

GMAIL_EMAIL = 'anshika31618@gmail.com'
GMAIL_APP_PASS = 'hlcv eobi tfwh terw'
PANEL_URL = 'https://ourproxy.sryze.cc'
PANEL_PASS = '7894561230'


def extract_otp_gmail(target_email: str, timeout: int = 120, after_timestamp: Optional[float] = None) -> Optional[str]:
    """Extract OTP from Gmail Spam folder.
    
    Sign-in OTP emails from AWS go to the Spam folder, NOT Inbox.
    Returns the 6-digit OTP code or None.
    """
    import imaplib, email, re
    from datetime import datetime, timedelta
    
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_EMAIL, GMAIL_APP_PASS)
        
        # Check Spam folder
        spam_folder = None
        status, data = mail.list()
        if status == 'OK':
            for item in data:
                if isinstance(item, bytes):
                    item = item.decode('utf-8', errors='ignore')
                if 'Spam' in item and 'HasNoChildren' in item:
                    # Extract folder name
                    m = re.search(r'\["?"([^"]*)"?\]\s*"?([^"]*)"?', item)
                    if m:
                        spam_folder = m.group(2)
                        break
        
        if not spam_folder:
            spam_folder = '[Gmail]/Spam'
        
        mail.select(f'"{spam_folder}"')
        
        # If after_timestamp is set, calculate the date
        if after_timestamp:
            since_dt = datetime.fromtimestamp(after_timestamp) - timedelta(seconds=30)  # 30s buffer
            since_date = since_dt.strftime('%d-%b-%Y')
        else:
            since_date = (datetime.now() - timedelta(minutes=60)).strftime('%d-%b-%Y')
        
        status, data = mail.search(None, f'(SINCE {since_date} FROM "no-reply@login.awsapps.com")')
        
        if status != 'OK' or not data[0]:
            # Fallback: broader search
            status, data = mail.search(None, '(FROM "no-reply@login.awsapps.com")')
        
        if status != 'OK' or not data[0]:
            return None
        
        msg_ids = data[0].split()
        # Get the most recent email
        for msg_id in reversed(msg_ids):
            status2, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status2 != 'OK':
                continue
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Check if it's addressed to our target or recent
            msg_date = msg.get('Date', '')
            # Try to parse date
            try:
                from email.utils import parsedate_to_datetime
                from datetime import timezone
                dt = parsedate_to_datetime(msg_date)
                now_aware = datetime.now(timezone.utc)
                age = (now_aware - dt).total_seconds()
                # Only accept emails less than 30 minutes old
                if age > 1800:
                    continue
                # If after_timestamp is set, only accept emails that arrived AFTER it
                if after_timestamp and dt.timestamp() < after_timestamp:
                    continue
            except Exception:
                # If date parsing fails, accept the email (don't filter)
                pass
            
            # Get body
            body = None
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype in ['text/html', 'text/plain']:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode('utf-8', errors='ignore')
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
            
            if not body:
                continue
            
            # Strip HTML tags
            clean_text = re.sub(r'<[^>]+>', ' ', body)
            clean_text = re.sub(r'\s+', ' ', clean_text)
            
            # Find 6-digit numbers
            matches = re.findall(r'(?<!\d)(\d{6})(?!\d)', clean_text)
            if matches:
                for m in matches:
                    # Skip false positives
                    if len(set(m)) == 1:  # 555555
                        continue
                    if m in ['123456', '234567', '345678', '456789', '012345']:
                        continue
                    mail.logout()
                    return m
                # If all filtered, use first
                if matches:
                    mail.logout()
                    return matches[0]
        
        mail.logout()
        return None
    except Exception as e:
        print(f"  [!] OTP extraction error: {e}")
        return None


def panel_login_ui(page, panel_url: str = PANEL_URL, panel_pass: str = PANEL_PASS) -> bool:
    """Login to panel via API."""
    # Navigate with retry
    nav_ok = False
    for attempt in range(3):
        try:
            page.goto(panel_url, wait_until='commit', timeout=60000)
            nav_ok = True
            break
        except Exception as e:
            print(f"  [*] Nav attempt {attempt+1} failed: {e}")
            time.sleep(3.0)
    
    if not nav_ok:
        print("  [!] Navigation failed after retries")
        return False
    time.sleep(3.0)
    
    r = page.evaluate(f"""async () => {{
        try {{
            const r = await fetch('/api/auth/login', {{
                method:'POST', headers:{{'Content-Type':'application/json'}},
                body: JSON.stringify({{password:{repr(panel_pass)}}})
            }});
            const text = await r.text();
            return {{ok: r.ok, status: r.status}};
        }} catch(e) {{ return {{ok:false, error:e.message}}; }}
    }}""")
    
    if r.get('ok'):
        try:
            page.goto(panel_url, wait_until='commit', timeout=30000)
        except Exception:
            pass  # Login succeeded even if redirect nav times out
        time.sleep(2.0)
        return True
    return False


def panel_add_account_ui(page, kiro_email, kiro_password, user_name=None) -> bool:
    """Add a Kiro account to the panel using the UI device auth flow.
    
    This uses the panel's modal-based device auth which is proven to work.
    """
    print(f"\n  ── PANEL ADD (UI Device Auth): {kiro_email} ──")
    
    # Step 1: Login to panel
    print("  [*] Logging into panel...")
    if not panel_login_ui(page, PANEL_URL):
        print("  [!] Panel login failed")
        return False
    
    # Step 2: Navigate to Kiro provider page
    print("  [*] Navigating to Kiro provider page...")
    try:
        page.goto(f"{PANEL_URL}/dashboard/providers/kiro", wait_until='domcontentloaded', timeout=60000)
    except Exception:
        try:
            page.goto(f"{PANEL_URL}/dashboard/providers/kiro", wait_until='commit', timeout=60000)
        except Exception:
            pass
    
    # Wait for SPA to fully load (look for 600+ buttons as indicator)
    button_count = 0
    for attempt in range(20):
        time.sleep(3.0)
        button_count = page.evaluate("() => document.querySelectorAll('button').length")
        if button_count > 500:
            print(f"  [+] Page loaded: {button_count} buttons")
            break
        if attempt < 19:
            print(f"  [*] Waiting for page load... ({button_count} buttons)")
    else:
        if button_count <= 500:
            print(f"  [!] Page didn't fully load ({button_count} buttons)")
            # Try a page reload
            print("  [*] Trying page reload...")
            page.reload(wait_until='domcontentloaded', timeout=30000)
            for attempt in range(10):
                time.sleep(3.0)
                button_count = page.evaluate("() => document.querySelectorAll('button').length")
                if button_count > 500:
                    print(f"  [+] Page loaded after reload: {button_count} buttons")
                    break
            else:
                print(f"  [!] Page still not loaded ({button_count} buttons)")
                return False
    
    # Step 3: Click "Add" button
    print("  [*] Clicking Add button...")
    
    # Debug: list all buttons containing 'add' text
    debug_btns = page.evaluate("""() => {
        const btns = document.querySelectorAll('button, [role="button"]');
        const result = [];
        for (const b of btns) {
            const t = (b.textContent || '').trim();
            if (t.toLowerCase().includes('add') || t.toLowerCase() === 'add') {
                result.push(t.substring(0, 50));
            }
        }
        return result;
    }""")
    print(f"  [*] Buttons with 'add': {debug_btns[:20]}")
    
    clicked = page.evaluate("""() => {
        const btns = document.querySelectorAll('button, [role="button"]');
        for (const b of btns) {
            const t = (b.textContent || '').trim();
            const tl = t.toLowerCase();
            // Match 'add' (with icon glyph) but not 'Add Model', 'Disable All', 'close'
            if (tl === 'add' || tl.startsWith('add') || tl.endsWith('add')) {
                if (tl.includes('model') || tl.includes('disable') || tl === 'close') continue;
                // Also skip if it's part of a longer word like 'added' or 'address'
                if (tl === 'add' || tl.startsWith('add ')) {
                    b.click();
                    return true;
                }
            }
        }
        // Fallback: broader match
        for (const b of btns) {
            const t = (b.textContent || '').trim();
            const tl = t.toLowerCase();
            if (tl === 'add' || (tl.startsWith('add') && tl.length <= 10)) {
                if (tl.includes('model') || tl.includes('disable')) continue;
                b.click();
                return true;
            }
        }
        return false;
    }""")
    
    if not clicked:
        print("  [!] Add button not found")
        return False
    print("  [+] Add button clicked")
    
    time.sleep(3.0)
    
    # Step 4: Click "AWS Builder ID" in modal
    print("  [*] Clicking AWS Builder ID...")
    aws_clicked = page.evaluate("""() => {
        const btns = document.querySelectorAll('button, [role="button"]');
        for (const b of btns) {
            const t = (b.textContent || '').trim().toLowerCase();
            if (t.includes('aws builder id') || t.includes('builder id')) {
                b.click();
                return true;
            }
        }
        return false;
    }""")
    
    if not aws_clicked:
        print("  [!] AWS Builder ID button not found")
        return False
    print("  [+] AWS Builder ID clicked")
    
    time.sleep(3.0)
    
    # Step 5: Extract Login URL from modal (retry with wait)
    print("  [*] Extracting login URL from modal...")
    modal_info = None
    for _retry in range(10):
        time.sleep(2.0)
        modal_info = page.evaluate("""() => {
            // Look for the modal content - the 'Connect Kiro' modal
            const modals = document.querySelectorAll('[class*="z-50"], [class*="fixed"]');
            for (const m of modals) {
                const text = m.innerText || '';
                if (!text || text.length < 30) continue;
                if (!text.includes('Kiro') && !text.includes('Connect')) continue;
                
                // Look for URL pattern
                const urlMatch = text.match(/https?:\/\/[^\s"']+awsapps[^\s"']*/);
                if (urlMatch) {
                    const codeMatch = urlMatch[0].match(/user_code=([A-Z]{4}-[A-Z]{4})/);
                    const code = codeMatch ? codeMatch[1] : '';
                    return {url: urlMatch[0], code: code, text: text.substring(0, 100)};
                }
            }
            
            // Fallback: search entire body for the URL
            const allText = document.body.innerText;
            const urlMatch = allText.match(/https?:\/\/[^\s"']+awsapps[^\s"']*/);
            if (urlMatch) {
                const codeMatch = urlMatch[0].match(/user_code=([A-Z]{4}-[A-Z]{4})/);
                return {url: urlMatch[0], code: codeMatch ? codeMatch[1] : '', text: ''};
            }
            
            // Last fallback: look for code element or link
            const links = document.querySelectorAll('a[href*="awsapps"]');
            if (links.length > 0) {
                const href = links[0].href;
                const codeMatch = href.match(/user_code=([A-Z]{4}-[A-Z]{4})/);
                return {url: href, code: codeMatch ? codeMatch[1] : '', text: ''};
            }
            
            return null;
        }""")
        
        if modal_info and modal_info.get('url'):
            break
    
    if not modal_info or not modal_info.get('url'):
        print("  [!] Could not extract login URL from modal after retries")
        # Take screenshot for debugging
        try:
            page.screenshot(path='/tmp/url_extract_debug.png')
        except:
            pass
        return False
    
    login_url = modal_info['url']
    user_code = modal_info.get('code', '')
    print(f"  [+] Login URL: {login_url}")
    print(f"  [+] User Code: {user_code}")
    
    # Step 6: Open NEW browser context for AWS login (no shared cookies with panel)
    print("  [*] Navigating to AWS login...")
    auth_browser = page.context.browser.new_context(viewport={'width': 1366, 'height': 768})
    auth_page = auth_browser.new_page()
    auth_page.set_default_timeout(60000)
    
    try:
        auth_page.goto(login_url, wait_until='load', timeout=60000)
    except Exception:
        try:
            auth_page.goto(login_url, wait_until='domcontentloaded', timeout=60000)
        except Exception:
            auth_page.goto(login_url, wait_until='commit', timeout=60000)
    
    # Wait for the page to redirect from device URL to sign-in page
    print("  [*] Waiting for redirect to sign-in page...")
    for _ in range(15):
        time.sleep(1.0)
        current_url = auth_page.url
        if 'signin' in current_url or 'login' in current_url:
            print(f"  [+] Redirected to: {current_url[:80]}")
            break
        try:
            title = auth_page.evaluate("() => document.title")
            if title and title != 'Amazon Web Services':
                print(f"  [+] Title changed to: {title}")
        except Exception:
            # Navigation in progress - page might have redirected
            time.sleep(2.0)
            if 'signin' in auth_page.url or 'login' in auth_page.url:
                print(f"  [+] Redirected to: {auth_page.url[:80]}")
                break
    
    current_url = auth_page.url
    print(f"  [+] Current URL: {current_url[:100]}")
    
    # Wait for the form to be fully rendered before filling
    print("  [*] Waiting for form to render...")
    for _ in range(10):
        time.sleep(2.0)
        try:
            input_count = auth_page.evaluate("""() => {
                const inputs = document.querySelectorAll('input');
                let vis_count = 0;
                for (const inp of inputs) {
                    if (inp.offsetWidth > 0 && inp.offsetHeight > 0) vis_count++;
                }
                return vis_count;
            }""")
            if input_count > 0:
                print(f"  [+] Form ready: {input_count} visible inputs")
                break
        except Exception:
            pass
    
    # Additional delay to let AWS session fully initialize
    time.sleep(5.0)
    
    # Step 7: Fill email
    print("  [*] Filling email...")
    
    # Wait for email input to appear (with retry)
    email_found = False
    for _ in range(10):
        time.sleep(2.0)
        input_count = auth_page.evaluate("""() => {
            const inputs = document.querySelectorAll('input');
            let vis_count = 0;
            for (const inp of inputs) {
                if (inp.offsetWidth > 0 && inp.offsetHeight > 0) vis_count++;
            }
            return vis_count;
        }""")
        if input_count > 0:
            email_found = True
            print(f"  [+] Found {input_count} visible inputs")
            break
    
    if not email_found:
        print("  [!] No visible inputs found after waiting")
        # Take screenshot for debugging
        try:
            auth_page.screenshot(path='/tmp/aws_login_debug.png')
            print("  [!] Screenshot saved to /tmp/aws_login_debug.png")
        except:
            pass
        auth_page.close()
        return False
    
    # Use native typing (more reliable than JS)
    email_filled = False
    try:
        email_loc = auth_page.locator('input:not([type="password"]):visible').first
        if email_loc.is_visible(timeout=5000):
            email_loc.click()
            time.sleep(0.5)
            email_loc.type(kiro_email, delay=30)
            email_filled = True
            print("  [+] Email typed natively")
    except Exception as e:
        print(f"  [!] Native fill failed: {e}")
    
    if not email_filled:
        # Fallback to JS fill
        email_filled = auth_page.evaluate("""(email) => {
            const inputs = document.querySelectorAll('input');
            for (const inp of inputs) {
                const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                if (!vis) continue;
                const type = (inp.type || '').toLowerCase();
                if (type === 'email' || type === 'text') {
                    inp.focus();
                    const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    s.call(inp, email);
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }
            }
            return false;
        }""", kiro_email)
        if email_filled:
            print("  [+] Email filled (JS fallback)")
    
    if not email_filled:
        print("  [!] Email not filled")
        auth_page.close()
        return False
    
    # Press Enter to submit (native keypress)
    auth_page.keyboard.press('Enter')
    time.sleep(8.0)  # Wait longer for navigation to complete
    
    # DEBUG: Print what the page shows after email submission
    debug_text = auth_page.evaluate("""() => {
        const body = (document.body?.innerText || '').toLowerCase();
        return body.substring(0, 300);
    }""")
    print(f"  [DEBUG] Page text after email submit: {debug_text}")
    
    # Handle "Enter your name" page (appears for some accounts)
    # Check multiple times as the page might take time to navigate
    name_page = False
    for _ in range(5):
        name_page = auth_page.evaluate("""() => {
            const body = (document.body?.innerText || '').toLowerCase();
            return body.includes('enter your name');
        }""")
        if name_page:
            print(f"  [DEBUG] Name page detected on iteration {_}")
            break
        time.sleep(2.0)
    
    # Also check for "enter your name" in different cases
    if not name_page:
        name_page_alt = auth_page.evaluate("""() => {
            const body = (document.body?.innerText || '');
            // Check with regex for case-insensitive match
            return /enter\s+your\s+name/i.test(body) || /your\s+name/i.test(body);
        }""")
        if name_page_alt:
            print(f"  [DEBUG] Name page detected via alt method")
            name_page = True
    
    if name_page:
        print("  [*] Enter your name page detected, filling name...")
        
        # Fill name field using fill() which is the most reliable
        name_filled = False
        name_val = user_name or f"{kiro_email.split('@')[0].title()} User"
        try:
            name_loc = auth_page.locator('input:not([type="password"]):visible').first
            if name_loc.is_visible(timeout=5000):
                # Use fill() - it's the most reliable Playwright method
                name_loc.fill(name_val)
                time.sleep(0.5)
                current_val = name_loc.input_value()
                print(f"  [+] Name input value: '{current_val}'")
                if current_val and len(current_val) > 2:
                    name_filled = True
                    print(f"  [+] Name filled: {name_val}")
        except Exception as e:
            print(f"  [!] Native name fill failed: {e}")
        
        if not name_filled:
            # Fallback to JS
            name_filled = auth_page.evaluate("""(name) => {
                const inputs = document.querySelectorAll('input');
                for (const inp of inputs) {
                    const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                    if (!vis) continue;
                    const type = (inp.type || '').toLowerCase();
                    if (type === 'text' || type === '') {
                        inp.focus();
                        inp.value = '';
                        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        s.call(inp, name);
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                }
                return false;
            }""", name_val)
            if name_filled:
                print("  [+] Name filled (JS fallback)")
        
        if name_filled:
            print("  [+] Name filled")
            # Click Continue button using mouse click (more reliable than JS click)
            continue_clicked = False
            try:
                # Find the Continue button using Playwright's locator
                continue_btn = auth_page.locator('button:has-text("Continue")').first
                if continue_btn.is_visible(timeout=5000):
                    continue_btn.click()
                    continue_clicked = True
                    print("  [+] Continue clicked (mouse)")
            except Exception:
                pass
            
            if not continue_clicked:
                # Fallback: try JS click
                continue_clicked = auth_page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const vis = b.offsetWidth > 0 && !b.disabled;
                        if (!vis) continue;
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (t.includes('continue')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                if continue_clicked:
                    print("  [+] Continue clicked (JS)")
                else:
                    print("  [!] Continue button not found, trying Enter...")
                    auth_page.keyboard.press('Enter')
            time.sleep(15.0)
            
            # If still on name page, check for ERR-837 and retry with refresh
            still_on_name = auth_page.evaluate("""() => {
                const body = (document.body?.innerText || '').toLowerCase();
                return {
                    onName: body.includes('enter your name'),
                    hasError: body.includes('err-837') || body.includes('sorry, there was an error')
                };
            }""")
            
            if still_on_name['onName']:
                print("  [!] Still on name page, retrying Continue multiple times...")
                # Try clicking Continue multiple times without refreshing
                for retry in range(5):
                    try:
                        continue_btn = auth_page.locator('button:has-text("Continue")').first
                        if continue_btn.is_visible(timeout=3000):
                            continue_btn.click()
                            print(f"  [+] Continue retry {retry+1} clicked")
                            time.sleep(8.0)
                            
                            # Check if we've moved past the name page
                            page_state = auth_page.evaluate("""() => {
                                const body = (document.body?.innerText || '').toLowerCase();
                                if (!body.includes('enter your name')) return 'moved_on';
                                if (body.includes('err-837') || body.includes('sorry')) return 'err';
                                return 'still_name';
                            }""")
                            print(f"  [*] Page state after retry {retry+1}: {page_state}")
                            if page_state == 'moved_on':
                                break
                    except Exception:
                        pass
                time.sleep(5.0)
        else:
            # Fallback: try clicking Continue anyway
            print("  [!] Name not filled, trying Continue...")
            auth_page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const vis = b.offsetWidth > 0 && !b.disabled;
                    if (!vis) continue;
                    const t = (b.textContent || '').trim().toLowerCase();
                    if (t.includes('continue')) {
                        b.click();
                        return true;
                    }
                }
                return false;
            }""")
            time.sleep(5.0)
    
    # Step 8: Check what page we're on - could be password OR email verification
    print("  [*] Determining next page...")
    time.sleep(3.0)
    
    page_state = auth_page.evaluate("""() => {
        const body = (document.body?.innerText || '').toLowerCase();
        if (body.includes('verify your email')) return 'otp_email_verify';
        if (body.includes('verify your identity')) return 'otp_identity_verify';
        // Check for password input manually (querySelectorAll doesn't support :visible)
        const pwInputs = document.querySelectorAll('input[type="password"]');
        for (const inp of pwInputs) {
            if (inp.offsetWidth > 0 && inp.offsetHeight > 0) return 'password';
        }
        if (body.includes('enter your name')) return 'name_page';
        if (body.includes('confirm') || body.includes('authorization')) return 'confirm';
        return body.substring(0, 100);
    }""")
    print(f"  [*] Page state: {page_state}")
    
    # Handle password page if present (for existing accounts)
    if page_state == 'password':
        print("  [*] On password page, filling password...")
        pw_filled = auth_page.evaluate("""(pw) => {
            const inputs = document.querySelectorAll('input[type="password"]');
            for (const inp of inputs) {
                const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                if (vis) {
                    inp.focus();
                    const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    s.call(inp, pw);
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }
            }
            return false;
        }""", kiro_password)
        
        if not pw_filled:
            print("  [!] Password not filled")
            auth_page.close()
            return False
        print("  [+] Password filled")
        auth_page.keyboard.press('Enter')
        time.sleep(8.0)
    
    # Handle OTP page (for both new accounts - email verify, and existing - identity verify)
    otp_page = auth_page.evaluate("""() => {
        const body = (document.body?.innerText || '').toLowerCase();
        return body.includes('verify your email') || body.includes('verify your identity');
    }""")
    
    # Record the time we expect the OTP to arrive (set to now since Continue was just clicked)
    otp_arrival_time = time.time()
    
    if otp_page:
        print("  [*] On OTP/verification page, waiting for fresh OTP from Gmail...")
        # Wait for fresh OTP - retry extraction multiple times with increasing delay
        otp = None
        for otp_retry in range(10):
            time.sleep(8.0)
            print(f"  [*] OTP retry {otp_retry+1}/10...")
            otp = extract_otp_gmail(kiro_email, timeout=120, after_timestamp=otp_arrival_time)
            if otp:
                print(f"  [+] Found fresh OTP: {otp}")
                break
            print(f"  [*] No fresh OTP yet, waiting...")
        
        if not otp:
            print("  [!] No fresh OTP found after 10 retries")
            try:
                auth_page.screenshot(path='/tmp/otp_missing.png')
            except:
                pass
            auth_page.close()
            return False
        
        print(f"  [+] OTP: {otp}")
        otp_filled = auth_page.evaluate("""(code) => {
                const inputs = document.querySelectorAll('input[type="text"], input[type="tel"], input[type="number"]');
                for (const inp of inputs) {
                    const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                    if (vis) {
                        inp.focus();
                        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        s.call(inp, code);
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                }
                return false;
            }""", otp)
            
        if otp_filled:
            print("  [+] OTP filled")
            auth_page.keyboard.press('Enter')
            time.sleep(12.0)  # Wait longer for page navigation after OTP
        else:
            print("  [!] OTP not filled")
            auth_page.close()
            return False
    
    # If we're not on an OTP page but also not on a confirm page, wait and check again
    if not otp_page:
        print("  [*] Checking page state again after wait...")
        time.sleep(5.0)
        
        # Re-check for OTP page
        otp_page = auth_page.evaluate("""() => {
            const body = (document.body?.innerText || '').toLowerCase();
            return body.includes('verify your email') || body.includes('verify your identity');
        }""")
        
        if otp_page:
            otp = extract_otp_gmail(kiro_email, timeout=60, after_timestamp=otp_arrival_time)
            if otp:
                otp_filled = auth_page.evaluate("""(code) => {
                    const inputs = document.querySelectorAll('input[type="text"], input[type="tel"], input[type="number"]');
                    for (const inp of inputs) {
                        const vis = inp.offsetWidth > 0 && inp.offsetHeight > 0 && !inp.disabled;
                        if (vis) {
                            inp.focus();
                            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            s.call(inp, code);
                            inp.dispatchEvent(new Event('input', {bubbles: true}));
                            inp.dispatchEvent(new Event('change', {bubbles: true}));
                            return true;
                        }
                    }
                    return false;
                }""", otp)
                if otp_filled:
                    auth_page.keyboard.press('Enter')
                    time.sleep(12.0)
    
    # Step 10: Click Confirm (with retries and multiple selectors)
    print("  [*] Clicking Confirm...")
    confirm_clicked = False
    
    for confirm_attempt in range(5):
        time.sleep(3.0)
        
        # Check current page state
        page_text = auth_page.evaluate("""() => (document.body?.innerText || '').toLowerCase()""")
        print(f"  [*] Confirm attempt {confirm_attempt+1}: {page_text[:60]}")
        
        # Try multiple button text patterns - be specific to avoid clicking wrong buttons
        confirm_clicked = auth_page.evaluate("""() => {
            const body = (document.body?.innerText || '').toLowerCase();
            // Only look for confirm button if we're on the Authorization requested page
            if (body.includes('authorization requested') || body.includes('confirm and continue')) {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const vis = b.offsetWidth > 0 && !b.disabled;
                    if (!vis) continue;
                    const t = (b.textContent || '').trim().toLowerCase();
                    if (t.includes('confirm and continue') || t === 'confirm') { b.click(); return true; }
                }
            }
            // If we see 'approved' or 'success', we're done
            if (body.includes('approved') || body.includes('request approved')) return true;
            return false;
        }""")
        
        if confirm_clicked:
            print("  [+] Confirm clicked")
            break
        
        # If we see "Request approved" or "approved", we're already done
        if 'approved' in page_text or 'success' in page_text:
            print("  [+] Already approved!")
            confirm_clicked = True
            break
    
    if not confirm_clicked:
        print("  [!] Confirm button not found after retries")
        try:
            auth_page.screenshot(path='/tmp/confirm_debug.png')
            print("  [!] Screenshot saved")
        except:
            pass
        auth_page.close()
        return False
    
    time.sleep(5.0)
    
    # Step 11: Click Allow
    print("  [*] Checking for Allow page...")
    time.sleep(3.0)
    
    # Check if we're on an Allow/permission page
    allow_needed = auth_page.evaluate("""() => {
        const body = (document.body?.innerText || '').toLowerCase();
        return body.includes('allow access') || body.includes('permissions requested') || 
               (body.includes('allow') && !body.includes('approved') && !body.includes('success'));
    }""")
    
    if allow_needed:
        print("  [*] Allow page detected, clicking Allow...")
        allow_clicked = auth_page.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const vis = b.offsetWidth > 0 && !b.disabled;
                if (!vis) continue;
                const t = (b.textContent || '').trim().toLowerCase();
                if (t.includes('allow') || t.includes('allow access')) {
                    b.click();
                    return true;
                }
            }
            return false;
        }""")
        
        if not allow_clicked:
            print("  [!] Allow button not found")
            try:
                auth_page.screenshot(path='/tmp/allow_debug.png')
            except:
                pass
            auth_page.close()
            return False
        print("  [+] Allow clicked")
    else:
        print("  [*] No Allow page needed (already approved or no permissions request)")
    
    time.sleep(5.0)
    
    # Step 12: Check for success
    final_text = auth_page.evaluate("() => document.body?.innerText || ''")
    print(f"  [+] Final page: {final_text[:100]}")
    
    success = 'Request approved' in final_text or 'approved' in final_text.lower()
    if success:
        print("  [+] Request approved!")
    else:
        print("  [!] Final state unclear")
        # Still might work - check panel
    
    auth_page.close()
    
    # Step 13: Verify on panel
    print("  [*] Verifying account on panel...")
    time.sleep(5.0)
    
    # Check provider count
    count_info = page.evaluate("""async () => {
        try {
            const r = await fetch('/api/providers', {credentials: 'include'});
            if (!r.ok) return {count: -1};
            const data = await r.json();
            return {count: Array.isArray(data) ? data.length : -1};
        } catch(e) { return {count: -1}; }
    }""")
    
    current_count = count_info.get('count', -1)
    print(f"  [+] Current panel count: {current_count}")
    
    if current_count > 95:  # Was 95 before our additions
        print("  ✅ Account added to panel!")
        return True
    elif success:
        print("  ✅ Auth succeeded, account likely added")
        return True
    else:
        print("  [!] Account may not have been added")
        return False
