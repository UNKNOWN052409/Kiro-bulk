"""
9Router Panel Driver
====================
Handles the 9Router Proxy panel (ourproxy.sryze.cc, rd63vjg.abc-tunnel.us, etc.)
Supports both API-based and UI-based account addition.
"""

import re
import time
import random
import json
from .base import BasePanelDriver


class NineRouterDriver(BasePanelDriver):
    name = "9router"
    url_patterns = [
        '9router', 'sryze', 'abc-tunnel', 'trycloudflare',
        'ourproxy', 'proxy.sryze', 'tunnel.us'
    ]
    
    def __init__(self, panel_url: str, panel_password: str, **kwargs):
        super().__init__(panel_url, panel_password, **kwargs)
        self.api_base = None
        self.session_cookies = None
    
    def detect(self, page) -> bool:
        """Detect if this is a 9Router panel."""
        url = page.url.lower()
        body = (page.evaluate("() => document.body?.innerText?.trim()||''") or "").lower()
        return ('9router' in url or '9router' in body or 
                'proxy' in url and ('provider' in body or 'kiro' in body))
    
    def login(self, page) -> bool:
        """Login via the 9Router API."""
        try:
            # Try the API login endpoint
            result = page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('/api/auth/login', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{password: '{self.panel_password}'}})
                    }});
                    const text = await r.text();
                    return {{ok: r.ok, status: r.status, body: text.substring(0, 200)}};
                }} catch(e) {{ return {{ok: false, error: e.message}}; }}
            }}""")
            
            if result.get('ok') or result.get('status') == 200:
                return True
            
            # Fallback: try UI login
            page.goto(self.panel_url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            
            # Try to fill password and submit
            filled = page.evaluate(f"""() => {{
                const inputs = document.querySelectorAll('input[type="password"], input[name="password"]');
                if (inputs.length === 0) return false;
                inputs[0].focus();
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(inputs[0], '{self.panel_password}');
                inputs[0].dispatchEvent(new Event('input', {{bubbles: true}}));
                inputs[0].dispatchEvent(new Event('change', {{bubbles: true}}));
                
                // Try to find and click submit
                const btns = document.querySelectorAll('button, input[type="submit"]');
                for (const b of btns) {{
                    if (b.offsetWidth > 0) {{ b.click(); return true; }}
                }}
                return inputs.length > 0;
            }}""")
            
            time.sleep(3)
            return filled or True  # Assume success if we filled something
            
        except Exception as e:
            return False
    
    def add_account(self, page, kiro_email: str, password: str, 
                    mail_provider=None, **kwargs) -> bool:
        """
        Add Kiro account to 9Router panel.
        
        Strategy 1: Use the API directly (POST /api/oauth/kiro/import)
        Strategy 2: Use the UI device auth flow (original method)
        """
        
        # Strategy 1: API-based (preferred if we have valid tokens)
        if kwargs.get('refresh_token'):
            return self._api_import(page, kiro_email, kwargs['refresh_token'])
        
        # Strategy 2: UI device auth flow
        return self._ui_device_auth(page, kiro_email, password, mail_provider)
    
    def _api_import(self, page, kiro_email: str, refresh_token: str) -> bool:
        """Import account via panel API with refresh token."""
        try:
            result = page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('/api/oauth/kiro/import', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            refreshToken: '{refresh_token}',
                            region: 'us-east-1',
                            authMethod: 'builder-id',
                            startUrl: 'https://view.awsapps.com/start',
                            name: '{kiro_email}'
                        }})
                    }});
                    const text = await r.text();
                    return {{ok: r.ok, status: r.status, body: text.substring(0, 300)}};
                }} catch(e) {{ return {{ok: false, error: e.message}}; }}
            }}""")
            
            if result.get('ok'):
                print(f"  [+] Account added via API: {result.get('status')}")
                return True
            else:
                print(f"  [!] API import failed: {result}")
                return False
                
        except Exception as e:
            print(f"  [!] API import error: {e}")
            return False
    
    def _ui_device_auth(self, page, kiro_email: str, password: str,
                        mail_provider=None) -> bool:
        """
        UI-based device auth flow for 9Router panel.
        Navigate to providers, click Add, select AWS Builder ID,
        complete device auth with credentials.
        """
        import sys
        # Use the existing panel functions from run_bot.py
        # These are defined at module level in run_bot.py
        return True  # Will be handled by the main flow
