"""
Universal Panel Driver
======================
Works with ANY panel by:
1. Searching for the provider (Kiro) in the panel UI
2. Finding the add mechanism (button, link, API)
3. Following the panel-specific flow to add the account
4. Extracting OTP/2FA when needed
"""

import re
import time
import random
from .base import BasePanelDriver


class UniversalPanelDriver(BasePanelDriver):
    """
    Universal driver that adapts to any panel structure.
    Uses intelligent UI exploration to find and use the add mechanism.
    """
    name = "universal"
    url_patterns = []  # Matches everything as fallback
    
    def detect(self, page) -> bool:
        """Universal driver matches anything."""
        return True
    
    def login(self, page) -> bool:
        """Generic login: try to find password input and submit."""
        try:
            page.goto(self.panel_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            
            # Try to find and fill password
            result = page.evaluate(f"""() => {{
                // Find password input
                const pwInputs = document.querySelectorAll('input[type="password"]');
                if (pwInputs.length === 0) return {{found: false}};
                
                const input = pwInputs[0];
                input.focus();
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(input, '{self.panel_password}');
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
                
                // Find submit button or form
                let submitted = false;
                
                // Try form submit
                const form = input.closest('form');
                if (form) {{
                    form.submit();
                    submitted = true;
                }}
                
                // Try nearby button
                if (!submitted) {{
                    const btns = input.parentElement.querySelectorAll('button, input[type="submit"], a.btn');
                    for (const b of btns) {{
                        if (b.offsetWidth > 0) {{ b.click(); submitted = true; break; }}
                    }}
                }}
                
                // Try page-level buttons
                if (!submitted) {{
                    const allBtns = document.querySelectorAll('button, input[type="submit"], [type="submit"]');
                    for (const b of allBtns) {{
                        const t = (b.textContent || b.value || '').trim().toLowerCase();
                        if (t.includes('login') || t.includes('sign') || t.includes('submit') || 
                            t.includes('enter') || t === '') {{
                            b.click();
                            submitted = true;
                            break;
                        }}
                    }}
                }}
                
                // Last resort: Enter key
                if (!submitted) {{
                    input.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', bubbles: true}}));
                    submitted = true;
                }}
                
                return {{found: true, submitted}};
            }}""")
            
            time.sleep(3)
            return result.get('found', False)
            
        except Exception as e:
            return False
    
    def add_account(self, page, kiro_email: str, password: str,
                    mail_provider=None, **kwargs) -> bool:
        """
        Universal add flow:
        1. Navigate to providers/settings section
        2. Find Kiro provider
        3. Click add/connect
        4. Follow whatever flow the panel presents
        5. Extract OTP if needed
        """
        # Step 1: Find the provider section
        provider_url = self._find_provider_section(page)
        if not provider_url:
            return False
        
        page.goto(provider_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(5)
        
        # Step 2: Find the add/connect button for Kiro
        add_info = page.evaluate("""() => {
            // Search for Kiro in page text
            const body = document.body.innerText || '';
            const kiroIndex = body.toLowerCase().indexOf('kiro');
            if (kiroIndex === -1) return {found: false};
            
            // Find clickable elements near 'kiro' text
            const candidates = [];
            const allEls = document.querySelectorAll('button, a, [role="button"], div, span, td, tr');
            for (const el of allEls) {
                const t = (el.textContent || '').trim().toLowerCase();
                if (t.includes('kiro') && el.offsetWidth > 0 && el.offsetHeight > 0) {
                    // Check for nearby add/connect buttons
                    const parent = el.closest('div, td, tr, li, section, article');
                    if (parent) {
                        const btns = parent.querySelectorAll('button, a, [role="button"]');
                        for (const b of btns) {
                            const bt = (b.textContent || '').trim().toLowerCase();
                            if (bt.includes('add') || bt.includes('connect') || 
                                bt.includes('enable') || bt.includes('link')) {
                                candidates.push({
                                    text: bt,
                                    el: b,
                                    found: true
                                });
                            }
                        }
                    }
                }
            }
            
            if (candidates.length > 0) return {found: true, candidates: candidates.length};
            
            // Fallback: look for any add button
            const addBtns = [];
            const allBtns = document.querySelectorAll('button, a, [role="button"]');
            for (const b of allBtns) {
                const t = (b.textContent || '').trim().toLowerCase();
                if ((t === 'add' || t.includes('add') || t.includes('+')) && 
                    b.offsetWidth > 0 && !b.disabled) {
                    addBtns.push(t);
                }
            }
            
            return {found: addBtns.length > 0, addButtons: addBtns.slice(0, 5)};
        }""")
        
        if not add_info.get('found'):
            return False
        
        # Step 3: Click the appropriate button and follow the flow
        # This is where panel-specific handling kicks in
        return self._follow_add_flow(page, kiro_email, password, mail_provider)
    
    def _find_provider_section(self, page) -> str:
        """Find the URL/section for Kiro provider in the panel."""
        try:
            # Check common patterns
            url = page.url
            base_url = url.split('?')[0]
            
            candidates = [
                f"{base_url}/providers",
                f"{base_url}/dashboard/providers",
                f"{base_url}/settings/providers",
                f"{base_url}/providers/kiro",
                f"{base_url}/dashboard/providers/kiro",
                f"{url}/providers",
                f"{url}/providers/kiro",
            ]
            
            for candidate in candidates:
                try:
                    result = page.evaluate(f"""async () => {{
                        try {{
                            const r = await fetch('{candidate}', {{credentials: 'include'}});
                            return {{ok: r.ok, status: r.status}};
                        }} catch(e) {{ return {{ok: false}}; }}
                    }}""")
                    if result.get('ok'):
                        return candidate
                except Exception:
                    pass
            
            return base_url  # Fallback to current page
            
        except Exception:
            return page.url
    
    def _follow_add_flow(self, page, kiro_email: str, password: str,
                         mail_provider=None) -> bool:
        """
        Follow whatever add flow the panel presents.
        Handles: device auth, OAuth popup, direct form, etc.
        """
        # Wait for any dialog/modal/popup to appear
        time.sleep(3)
        
        # Check what appeared on screen
        page_text = page.evaluate("() => document.body.innerText || ''")
        
        # Check for device auth URL pattern
        device_url_match = re.search(r'https://[^\s]+\.awsapps\.com[^\s]*', page_text)
        if device_url_match:
            return self._handle_device_auth(page, device_url_match.group(0), 
                                            kiro_email, password, mail_provider)
        
        # Check for OAuth popup
        popup_url_match = re.search(r'https://accounts\.google\.com[^\s"\'()]*', page_text)
        if popup_url_match:
            return self._handle_oauth_popup(page, kiro_email, password, mail_provider)
        
        # Check for direct form (email + password fields)
        has_email_input = page.evaluate("() => !!document.querySelector('input[type=\"email\"], input[name=\"email\"]')")
        if has_email_input:
            return self._handle_direct_form(page, kiro_email, password, mail_provider)
        
        # Check for verification/OTP fields
        has_otp_input = page.evaluate("() => !!document.querySelector('input[type=\"text\"], input[name=\"code\"], input[name=\"otp\"]')")
        if has_otp_input and mail_provider:
            return self._handle_otp_only(page, mail_provider)
        
        return False
    
    def _handle_device_auth(self, page, device_url: str, kiro_email: str,
                           password: str, mail_provider=None) -> bool:
        """Handle AWS device auth flow."""
        auth_page = page.context.new_page()
        try:
            auth_page.goto(device_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            
            # Fill email
            email_filled = auth_page.evaluate(f"""(email) => {{
                const inputs = document.querySelectorAll('input[type="email"]');
                if (inputs.length === 0) return false;
                inputs[0].focus();
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(inputs[0], email);
                inputs[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                inputs[0].dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
            }}""", kiro_email)
            
            time.sleep(1)
            auth_page.keyboard.press('Enter')
            time.sleep(5)
            
            # Handle OTP if needed
            if mail_provider:
                otp_code = mail_provider.get_otp(kiro_email, timeout=60)
                if otp_code:
                    auth_page.evaluate(f"""(code) => {{
                        const inputs = document.querySelectorAll('input[type="text"], input[type="tel"], input[name="code"]');
                        for (const inp of inputs) {{
                            if (inp.offsetWidth > 0) {{
                                inp.focus();
                                const setter = Object.getOwnPropertyDescriptor(
                                    window.HTMLInputElement.prototype, 'value').set;
                                setter.call(inp, code);
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                                return true;
                            }}
                        }}
                        return false;
                    }}""", otp_code)
                    time.sleep(1)
                    auth_page.keyboard.press('Enter')
                    time.sleep(3)
            
            # Fill password
            auth_page.evaluate(f"""(pw) => {{
                const inputs = document.querySelectorAll('input[type="password"]');
                if (inputs.length === 0) return false;
                inputs[0].focus();
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(inputs[0], pw);
                inputs[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                inputs[0].dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
            }}""", password)
            
            time.sleep(1)
            auth_page.keyboard.press('Enter')
            time.sleep(5)
            
            # Click Allow/Authorize if present
            auth_page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    const t = (b.textContent || '').trim().toLowerCase();
                    if (t.includes('allow') || t.includes('authorize') || 
                        t.includes('confirm') || t.includes('trust')) {
                        if (b.offsetWidth > 0) { b.click(); return true; }
                    }
                }
                return false;
            }""")
            
            time.sleep(5)
            auth_page.close()
            return True
            
        except Exception as e:
            try:
                auth_page.close()
            except Exception:
                pass
            return False
    
    def _handle_oauth_popup(self, page, kiro_email: str, password: str,
                           mail_provider=None) -> bool:
        """Handle OAuth popup flow (Google/GitHub)."""
        # The popup should already be open or will open
        time.sleep(3)
        
        # Get all pages in context
        pages = page.context.pages
        auth_page = None
        for p in pages:
            if 'accounts.google' in p.url or 'github' in p.url:
                auth_page = p
                break
        
        if not auth_page:
            return False
        
        # Follow the OAuth flow on the popup
        return self._handle_device_auth(auth_page, auth_page.url, kiro_email, 
                                        password, mail_provider)
    
    def _handle_direct_form(self, page, kiro_email: str, password: str,
                           mail_provider=None) -> bool:
        """Handle direct email/password form."""
        result = page.evaluate(f"""(email, pw) => {{
            // Fill email
            const emailInputs = document.querySelectorAll('input[type="email"], input[name="email"]');
            if (emailInputs.length > 0) {{
                emailInputs[0].focus();
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(emailInputs[0], email);
                emailInputs[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                emailInputs[0].dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
            
            // Fill password
            const pwInputs = document.querySelectorAll('input[type="password"]');
            if (pwInputs.length > 0) {{
                pwInputs[0].focus();
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(pwInputs[0], pw);
                pwInputs[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                pwInputs[0].dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
            
            // Submit
            const form = document.querySelector('form');
            if (form) {{ form.submit(); return true; }}
            
            const btns = document.querySelectorAll('button, input[type="submit"]');
            for (const b of btns) {{
                if (b.offsetWidth > 0) {{ b.click(); return true; }}
            }}
            
            return emailInputs.length > 0;
        }}""", kiro_email, password)
        
        time.sleep(5)
        
        # Handle OTP if present
        if mail_provider:
            otp_present = page.evaluate("() => !!document.querySelector('input[name=\"code\"], input[name=\"otp\"], input[placeholder*=\"code\"], input[placeholder*=\"OTP\"]')")
            if otp_present:
                otp_code = mail_provider.get_otp(kiro_email, timeout=60)
                if otp_code:
                    page.evaluate(f"""(code) => {{
                        const inputs = document.querySelectorAll('input[name="code"], input[name="otp"], input[placeholder*="code" i], input[placeholder*="otp" i], input[type="text"]');
                        for (const inp of inputs) {{
                            if (inp.offsetWidth > 0) {{
                                inp.focus();
                                const setter = Object.getOwnPropertyDescriptor(
                                    window.HTMLInputElement.prototype, 'value').set;
                                setter.call(inp, code);
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                                return true;
                            }}
                        }}
                        return false;
                    }}""", otp_code)
                    time.sleep(1)
                    page.keyboard.press('Enter')
                    time.sleep(5)
        
        return result
    
    def _handle_otp_only(self, page, mail_provider) -> bool:
        """Handle OTP-only verification (already logged in)."""
        otp_code = mail_provider.get_otp(timeout=60)
        if not otp_code:
            return False
        
        page.evaluate(f"""(code) => {{
            const inputs = document.querySelectorAll('input[type="text"], input[type="tel"], input[name="code"], input[name="otp"]');
            for (const inp of inputs) {{
                if (inp.offsetWidth > 0) {{
                    inp.focus();
                    const setter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    setter.call(inp, code);
                    inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                    inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }}
            }}
            return false;
        }}""", otp_code)
        
        time.sleep(1)
        page.keyboard.press('Enter')
        time.sleep(5)
        return True
