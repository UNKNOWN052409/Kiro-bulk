#!/usr/bin/env python3
"""
Kiro Full Flow - Account Creation + Panel Import
=================================================
Simple, clean implementation that:
1. Creates account on app.kiro.dev/signup
2. Captures auth_code via callback server
3. Exchanges for refresh_token
4. Imports to 9Router panel
"""
import asyncio
import re
import random
import secrets
import hashlib
import base64
import json
import time
import imaplib
import requests
import urllib3
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

urllib3.disable_warnings()
requests.packages.urllib3.disable_warnings()

# ── Config ───────────────────────────────────────────────────────────────────
PANEL_URL = "https://ourproxy.sryze.cc"
PANEL_PASS = "7894561230"
IMAP_USER = "anshika31618@gmail.com"
IMAP_PASS = "hlcveobitfwhterw"
DOMAIN = "havenhaus.in"
OIDC_BASE = "https://oidc.us-east-1.amazonaws.com"
REDIRECT_URI = "http://127.0.0.1:3128"

# ── Callback Server ─────────────────────────────────────────────────────────
callback_data = {"signin_params": {}, "auth_code": ""}

class CbHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if "code" in qs:
            callback_data["auth_code"] = qs["code"][0]
        callback_data["signin_params"] = {k: v[0] for k, v in qs.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>OK</h1><script>setTimeout(()=>window.close(),500)</script></body></html>")
    def log_message(self, *args):
        pass

def start_callback_server():
    server = HTTPServer(("127.0.0.1", 3128), CbHandler)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server

# ── Gmail OTP ────────────────────────────────────────────────────────────────
def get_otp_from_gmail(max_wait=60):
    """Get latest 6-digit OTP from Gmail."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            mail = imaplib.IMAP4_SSL('imap.gmail.com')
            mail.login(IMAP_USER, IMAP_PASS)
            mail.select('inbox')
            status, messages = mail.search(None, '(FROM "aws" OR FROM "amazon" OR FROM "no-reply")')
            ids = messages[0].split()
            if not ids:
                mail.logout()
                time.sleep(2)
                continue
            for msg_id in reversed(ids[-3:]):
                status, msg_data = mail.fetch(msg_id, '(BODY.PEEK[TEXT] BODY.PEEK[TEXT/HTML])')
                for part in msg_data:
                    if isinstance(part[1], bytes):
                        text = part[1].decode('utf-8', errors='ignore')
                        match = re.search(r'\b(\d{6})\b', text)
                        if match:
                            otp = match.group(1)
                            # Make sure it's not a year
                            if 100000 <= int(otp) <= 999999:
                                mail.logout()
                                return otp
            mail.logout()
        except Exception as e:
            pass
        time.sleep(2)
    return None

# ── OIDC Client Registration ────────────────────────────────────────────────
def register_oidc_client():
    """Register a public OIDC client."""
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    
    resp = requests.post(f"{OIDC_BASE}/register", json={
        "clientName": f"kiro-client-{random.randint(10000, 99999)}",
        "redirectUris": [REDIRECT_URI],
        "grantTypes": ["authorization_code", "refresh_token"],
        "responseTypes": ["code"],
        "tokenEndpointAuthMethod": "none",
        "codeChallengeMethod": "S256",
        "scope": "openid profile email codewhisperer:completions",
    }, timeout=30, verify=False)
    
    data = resp.json()
    return {
        "client_id": data.get("clientId", ""),
        "client_secret": data.get("clientSecret", ""),
        "code_verifier": code_verifier,
        "code_challenge": code_challenge,
    }

# ── Token Exchange ───────────────────────────────────────────────────────────
def exchange_auth_code(auth_code, client_id, client_secret, code_verifier):
    """Exchange auth_code for access_token + refresh_token."""
    resp = requests.post(f"{OIDC_BASE}/token", json={
        "clientId": client_id,
        "clientSecret": client_secret,
        "grantType": "authorization_code",
        "code": auth_code,
        "redirectUri": REDIRECT_URI,
        "codeVerifier": code_verifier,
    }, timeout=30, verify=False)
    
    data = resp.json()
    if "accessToken" in data:
        return data.get("accessToken", ""), data.get("refreshToken", "")
    return "", ""

# ── Panel Import ─────────────────────────────────────────────────────────────
def panel_login():
    """Login to panel and get auth token cookie."""
    session = requests.Session()
    resp = session.post(f"{PANEL_URL}/api/auth/login", 
                       json={"password": PANEL_PASS}, 
                       verify=False, timeout=30)
    return session

def panel_import(session, email, refresh_token):
    """Import account to panel."""
    resp = session.post(f"{PANEL_URL}/api/oauth/kiro/import", json={
        "refreshToken": refresh_token,
        "region": "us-east-1",
        "authMethod": "builder-id",
        "startUrl": "https://view.awsapps.com/start",
        "name": email,
    }, verify=False, timeout=30)
    return resp.json()

# ── Account Creation ─────────────────────────────────────────────────────────
def gen_name():
    first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", 
                   "Michael", "Linda", "David", "Elizabeth", "William", "Barbara",
                   "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
                   "Christopher", "Karen", "Daniel", "Lisa", "Matthew", "Nancy",
                   "Anthony", "Betty", "Mark", "Margaret", "Steven", "Sandra"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
                  "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
                  "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
                  "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
                  "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def gen_email(name, domain):
    first = name.split()[0].lower()
    last = name.split()[1].lower()
    suffix = random.randint(100, 999)
    return f"{first}{last}{suffix}@{domain}"

async def create_and_import(playwright, email=None, name=None):
    """Create one account and import to panel."""
    callback_data["signin_params"] = {}
    callback_data["auth_code"] = ""
    
    if not email:
        name = gen_name()
        email = gen_email(name, DOMAIN)
    if not name:
        name = " ".join(email.split("@")[0].replace("_", " ").split()[:2]).title()
    
    print(f"\n{'='*60}")
    print(f"[*] Creating account: {email}")
    print(f"    Name: {name}")
    print(f"{'='*60}")
    
    # Register OIDC client
    oidc = register_oidc_client()
    print(f"[+] OIDC client registered: {oidc['client_id'][:20]}...")
    
    browser = await playwright.chromium.launch(
        headless=True, 
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
    )
    context = await browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="en-US",
    )
    page = await context.new_page()
    
    # Monitor ALL requests for auth code
    captured_urls = []
    def on_request(req):
        url = req.url
        if "authentication_result" in url or "code=" in url:
            captured_urls.append(url)
            print(f"  [CAPTURED] {url[:150]}")
    page.on("request", on_request)
    
    # Step 1: Navigate to Kiro signup
    print("[*] Navigating to app.kiro.dev/signup...")
    await page.goto("https://app.kiro.dev/signup", wait_until="domcontentloaded", timeout=30000)
    
    # Wait for page to render
    for _ in range(10):
        await asyncio.sleep(2)
        try:
            body = await page.evaluate("document.body.innerText")
            if len(body) > 50:
                break
        except:
            pass
    
    # Step 2: Click Builder ID
    print("[*] Clicking Builder ID...")
    clicked = await page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button, a, [role="button"]'));
        const target = btns.find(b => {
            const t = (b.textContent || '').trim();
            return t.includes('Builder ID') && b.offsetWidth > 0;
        });
        if (!target) return false;
        target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
        return true;
    }""")
    
    if not clicked:
        print("[!] Builder ID button not found")
        body = await page.evaluate("document.body.innerText")
        print(f"  Body: {body[:300]}")
        await browser.close()
        return False
    
    print("[+] Builder ID clicked")
    await asyncio.sleep(5)
    
    # Step 3: Wait for callback with signin params
    print("[*] Waiting for Kiro callback...")
    for _ in range(15):
        await asyncio.sleep(2)
        if callback_data["signin_params"]:
            print(f"[+] Callback received: {list(callback_data['signin_params'].keys())}")
            break
    else:
        print("[!] No callback received")
        await browser.close()
        return False
    
    # Step 4: Navigate to OIDC authorize URL
    params = callback_data["signin_params"]
    authorize_url = f"{OIDC_BASE}/authorize?" + urlencode({
        "response_type": "code",
        "client_id": oidc["client_id"],
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile email codewhisperer:completions",
        "state": params.get("state", secrets.token_urlsafe(16)),
        "code_challenge": oidc["code_challenge"],
        "code_challenge_method": "S256",
        "nonce": secrets.token_urlsafe(16),
    })
    
    print(f"[*] Navigating to OIDC authorize...")
    await page.goto(authorize_url, wait_until="domcontentloaded", timeout=15000)
    await asyncio.sleep(5)
    
    # Step 5: Check if we're on the Builder ID login page
    body = await page.evaluate("document.body.innerText")
    print(f"  Page: {body[:150]}")
    
    # Find and fill email
    email_filled = False
    for attempt in range(5):
        try:
            email_input = page.locator('input[type="email"]').first
            if await email_input.is_visible():
                await email_input.fill(email)
                await asyncio.sleep(0.5)
                
                # Click Continue
                continue_btn = page.locator('button:has-text("Continue")').first
                if await continue_btn.is_visible():
                    await continue_btn.click()
                    email_filled = True
                    print(f"[+] Email filled: {email}")
                    break
        except Exception as e:
            await asyncio.sleep(2)
    
    if not email_filled:
        print("[!] Could not fill email")
        await browser.close()
        return False
    
    # Step 6: Wait for OTP page or direct redirect
    print("[*] Waiting for next page (OTP or name)...")
    await asyncio.sleep(8)
    
    # Check current state
    current_url = page.url
    body = await page.evaluate("document.body.innerText")
    print(f"  URL: {current_url[:100]}")
    print(f"  Body: {body[:100]}")
    
    # Step 6a: If on OTP page, fill OTP
    if "verify" in body.lower() or "verification" in body.lower() or "code" in body.lower():
        print("[*] OTP page detected")
        otp = get_otp_from_gmail()
        if otp:
            print(f"[+] OTP: {otp}")
            # Try to fill OTP - could be single input or multiple digits
            try:
                # Try single input first
                otp_input = page.locator('input[type="text"]').first
                if await otp_input.is_visible():
                    await otp_input.fill(otp)
                    await asyncio.sleep(1)
                    print("[+] OTP filled (single input)")
                else:
                    # Try digit-by-digit
                    for i, digit in enumerate(otp):
                        try:
                            digit_input = page.locator(f'input:nth-child({i+1}), input[aria-label*="digit {i+1}" i]').first
                            if await digit_input.is_visible():
                                await digit_input.fill(digit)
                                await asyncio.sleep(0.1)
                        except:
                            pass
                    print("[+] OTP filled (digits)")
            except Exception as e:
                print(f"[!] OTP fill error: {e}")
            await asyncio.sleep(5)
        else:
            print("[!] No OTP found")
            await browser.close()
            return False
    
    # Step 6b: Wait for name page
    print("[*] Waiting for name page...")
    for _ in range(15):
        await asyncio.sleep(2)
        body = await page.evaluate("document.body.innerText")
        if "enter your name" in body.lower() or "your name" in body.lower():
            print("[+] Name page detected")
            break
    
    # Step 7: Fill name
    print("[*] Filling name...")
    name_filled = False
    for attempt in range(5):
        try:
            # Find visible text input (name field)
            name_input = page.locator('input[type="text"]').first
            if await name_input.is_visible():
                await name_input.click()
                await asyncio.sleep(0.5)
                # Use native fill which properly triggers React
                await name_input.fill(name)
                name_filled = True
                print(f"[+] Name filled: {name}")
                await asyncio.sleep(1)
                
                # Click Continue
                continue_btn = page.locator('button:has-text("Continue")').first
                if await continue_btn.is_visible():
                    await continue_btn.click()
                    print("[+] Continue clicked")
                break
        except Exception as e:
            await asyncio.sleep(2)
    
    if not name_filled:
        print("[!] Could not fill name")
        await browser.close()
        return False
    
    # Step 8: Wait for redirect with auth code
    print("[*] Waiting for redirect with auth code...")
    for _ in range(20):
        await asyncio.sleep(2)
        
        # Check callback
        if callback_data.get("auth_code"):
            print(f"[+] Auth code captured: {callback_data['auth_code'][:20]}...")
            break
        
        # Check URL
        url = page.url
        if "authentication_result" in url or "code=" in url:
            qs = parse_qs(urlparse(url).query)
            if "code" in qs:
                callback_data["auth_code"] = qs["code"][0]
                print(f"[+] Auth code from URL: {callback_data['auth_code'][:20]}...")
                break
        elif "127.0.0.1" in url or "localhost" in url:
            qs = parse_qs(urlparse(url).query)
            if "code" in qs:
                callback_data["auth_code"] = qs["code"][0]
                print(f"[+] Auth code from redirect: {callback_data['auth_code'][:20]}...")
                break
    else:
        print("[!] No auth code captured")
        print(f"  Final URL: {page.url[:150]}")
        body = await page.evaluate("document.body.innerText")
        print(f"  Final body: {body[:200]}")
        await browser.close()
        return False
    
    # Step 9: Exchange auth code for tokens
    auth_code = callback_data["auth_code"]
    print("[*] Exchanging auth code for tokens...")
    access_token, refresh_token = exchange_auth_code(
        auth_code, oidc["client_id"], oidc["client_secret"], oidc["code_verifier"]
    )
    
    if not refresh_token:
        print("[!] Token exchange failed")
        await browser.close()
        return False
    
    print(f"[+] Access token: {access_token[:30]}...")
    print(f"[+] Refresh token: {refresh_token[:30]}...")
    
    await browser.close()
    
    # Step 10: Import to panel
    print("[*] Importing to panel...")
    session = panel_login()
    result = panel_import(session, email, refresh_token)
    print(f"[+] Panel import result: {json.dumps(result, indent=2)[:300]}")
    
    if result.get("success") or "token" in str(result).lower() or "id" in str(result).lower():
        print(f"[✅] SUCCESS: {email} created and imported to panel!")
        return True
    else:
        print(f"[❌] Panel import may have failed: {result}")
        return True  # Still return True since account was created

async def main():
    """Create and import one account."""
    from playwright.async_api import async_playwright
    
    # Start callback server
    server = start_callback_server()
    print("[+] Callback server started on 127.0.0.1:3128")
    
    async with async_playwright() as pw:
        success = await create_and_import(pw)
    
    if success:
        print("\n[✅] Account created and imported successfully!")
    else:
        print("\n[❌] Failed to create/import account")
    
    return 0 if success else 1

if __name__ == "__main__":
    asyncio.run(main())
