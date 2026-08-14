#!/usr/bin/env python3
"""Kiro Full Flow v4 - Correct OIDC PKCE approach"""
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

PANEL_URL = "https://ourproxy.sryze.cc"
PANEL_PASS = "7894561230"
IMAP_USER = "anshika31618@gmail.com"
IMAP_PASS = "hlcveobitfwhterw"
DOMAIN = "havenhaus.in"
OIDC_BASE = "https://oidc.us-east-1.amazonaws.com"
REDIRECT_URI = "http://127.0.0.1:3128"
ISSUER_URL = "https://view.awsapps.com/start/"
SCOPES = [
    "codewhisperer:completions", "codewhisperer:analysis",
    "codewhisperer:conversations", "codewhisperer:transformations",
    "codewhisperer:taskassist",
]

callback_data = {"auth_code": "", "signin_params": {}}

class CbHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        code = qs.get("code", [""])[0]
        if code:
            callback_data["auth_code"] = code
            print("    [CB] Auth code captured!")
        if "signin/callback" in parsed.path or qs.get("login_option"):
            callback_data["signin_params"] = {k: v[0] for k, v in qs.items()}
            print(f"    [CB] Signin params: {list(qs.keys())}")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><p>OK</p></body></html>")
    def log_message(self, *args):
        pass

def start_callback_server():
    server = HTTPServer(("127.0.0.1", 3128), CbHandler)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server

def get_otp_from_gmail(max_wait=60):
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
                            if 100000 <= int(otp) <= 999999:
                                mail.logout()
                                return otp
            mail.logout()
        except:
            pass
        time.sleep(2)
    return None

def register_oidc_client():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()
    state_val = secrets.token_urlsafe(32)
    
    resp = requests.post(f"{OIDC_BASE}/client/register", json={
        "clientName": "Kiro IDE",
        "clientType": "public",
        "grantTypes": ["authorization_code", "refresh_token"],
        "issuerUrl": ISSUER_URL,
        "redirectUris": [REDIRECT_URI],
        "scopes": SCOPES,
    }, timeout=25, verify=False)
    
    reg = resp.json()
    if "clientId" not in reg:
        print(f"[!] OIDC registration failed: {reg}")
        return None
    
    return {
        "client_id": reg["clientId"],
        "client_secret": reg["clientSecret"],
        "code_verifier": code_verifier,
        "code_challenge": code_challenge,
        "state_val": state_val,
        "signin_url": f"https://app.kiro.dev/signin?" + urlencode({
            "state": state_val,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "redirect_uri": REDIRECT_URI,
            "redirect_from": "KiroIDE",
        }),
    }

def exchange_auth_code(auth_code, client_id, client_secret, code_verifier):
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

def gen_name():
    first = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "David", "Elizabeth"]
    last = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    return f"{random.choice(first)} {random.choice(last)}"

def gen_email(name, domain):
    first = name.split()[0].lower()
    last = name.split()[1].lower()
    return f"{first}{last}{random.randint(100, 999)}@{domain}"

async def run_flow(playwright):
    callback_data["auth_code"] = ""
    callback_data["signin_params"] = {}
    
    name = gen_name()
    email = gen_email(name, DOMAIN)
    print(f"\n{'='*60}")
    print(f"[*] Account: {email} / {name}")
    print(f"{'='*60}")
    
    # Register OIDC client
    oidc = register_oidc_client()
    if not oidc:
        return False
    print(f"[+] OIDC client: {oidc['client_id'][:20]}...")
    
    browser = await playwright.chromium.launch(
        headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    page = await browser.new_page(
        viewport={"width": 1366, "height": 768},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    
    # Step 1: Navigate to Kiro signin with OIDC params
    print("[*] Navigating to Kiro signin with OIDC params...")
    await page.goto(oidc["signin_url"], wait_until="domcontentloaded", timeout=30000)
    
    # Wait for callback with signin params
    print("[*] Waiting for Kiro callback...")
    for _ in range(15):
        await asyncio.sleep(2)
        if callback_data["signin_params"]:
            print(f"[+] Signin params received: {list(callback_data['signin_params'].keys())}")
            break
    else:
        print("[!] No signin callback received")
        print(f"  Current URL: {page.url[:100]}")
        await browser.close()
        return False
    
    # Step 2: Navigate to OIDC authorize URL
    params = callback_data["signin_params"]
    authorize_url = f"{OIDC_BASE}/authorize?" + urlencode({
        "response_type": "code",
        "client_id": oidc["client_id"],
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES + ["openid", "profile", "email"]),
        "state": params.get("state", oidc["state_val"]),
        "code_challenge": oidc["code_challenge"],
        "code_challenge_method": "S256",
        "nonce": secrets.token_urlsafe(16),
    })
    
    print(f"[*] Navigating to OIDC authorize...")
    await page.goto(authorize_url, wait_until="domcontentloaded", timeout=15000)
    await asyncio.sleep(5)
    
    # Step 3: Check if on AWS Builder ID page
    body = await page.evaluate("document.body.innerText")
    url = page.url
    print(f"  URL: {url[:100]}")
    print(f"  Body: {body[:100]}")
    
    if "signin.aws" not in url and "profile.aws" not in url:
        print("[!] Not on AWS page")
        await browser.close()
        return False
    
    # Wait for page to render
    for _ in range(10):
        await asyncio.sleep(2)
        body = await page.evaluate("document.body.innerText")
        if len(body) > 30 and ("email" in body.lower() or "name" in body.lower() or "get started" in body.lower()):
            break
    
    # Step 4: Fill email
    print("[*] Filling email...")
    email_filled = False
    for attempt in range(8):
        try:
            email_input = page.locator('input[type="email"]').first
            if await email_input.is_visible(timeout=3000):
                await email_input.click()
                await asyncio.sleep(0.5)
                await email_input.fill(email)
                await asyncio.sleep(0.5)
                val = await email_input.input_value()
                if val == email:
                    continue_btn = page.locator('button:has-text("Continue")').first
                    if await continue_btn.is_visible(timeout=3000):
                        await continue_btn.click()
                        email_filled = True
                        print(f"[+] Email filled: {email}")
                        break
        except:
            await asyncio.sleep(2)
    
    if not email_filled:
        print("[!] Email fill failed")
        await browser.close()
        return False
    
    # Step 5: Wait for OTP or name page
    print("[*] Waiting for next step...")
    for _ in range(15):
        await asyncio.sleep(3)
        body = await page.evaluate("document.body.innerText")
        url = page.url
        
        if "enter your name" in body.lower() or "your name" in body.lower():
            print("[+] Name page")
            break
        elif "verification" in body.lower() or "one-time" in body.lower():
            print("[+] OTP page")
            break
        elif "err-837" in body.lower():
            print("[!] ERR-837")
            break
        elif "allow" in body.lower() and "kiro" in body.lower():
            print("[+] Consent page")
            break
        elif "127.0.0.1" in url or "localhost" in url:
            print("[+] Callback redirect")
            break
    
    body = await page.evaluate("document.body.innerText")
    
    # Step 5a: Fill OTP if needed
    if "verification" in body.lower() or "one-time" in body.lower():
        print("[*] Getting OTP...")
        otp = get_otp_from_gmail()
        if otp:
            print(f"[+] OTP: {otp}")
            try:
                otp_input = page.locator('input[type="text"]').first
                if await otp_input.is_visible(timeout=3000):
                    await otp_input.click()
                    await asyncio.sleep(0.3)
                    await otp_input.fill("")
                    await asyncio.sleep(0.2)
                    await otp_input.press_sequentially(otp)
                    print("[+] OTP filled")
                    await asyncio.sleep(5)
            except Exception as e:
                print(f"[!] OTP error: {e}")
        else:
            print("[!] No OTP")
            await browser.close()
            return False
    
    # Step 6: Wait for name page
    print("[*] Waiting for name page...")
    for _ in range(15):
        await asyncio.sleep(2)
        body = await page.evaluate("document.body.innerText")
        url = page.url
        
        if "enter your name" in body.lower():
            print("[+] Name page detected")
            break
        elif "allow" in body.lower() and "kiro" in body.lower():
            print("[+] Consent page")
            break
        elif "127.0.0.1" in url or "localhost" in url:
            print(f"[+] Redirect: {url[:100]}")
            break
        elif "err-837" in body.lower():
            print("[!] ERR-837")
            break
    
    body = await page.evaluate("document.body.innerText")
    print(f"  Body: {body[:150]}")
    
    # Step 7: Fill name
    if "enter your name" in body.lower():
        print("[*] Filling name...")
        name_filled = False
        for attempt in range(5):
            try:
                name_input = page.locator('input[type="text"]').first
                if await name_input.is_visible(timeout=3000):
                    await name_input.click()
                    await asyncio.sleep(0.5)
                    await name_input.fill(name)
                    name_filled = True
                    print(f"[+] Name filled: {name}")
                    await asyncio.sleep(1)
                    
                    continue_btn = page.locator('button:has-text("Continue")').first
                    if await continue_btn.is_visible(timeout=3000):
                        await continue_btn.click()
                        print("[+] Continue clicked")
                    break
            except:
                await asyncio.sleep(2)
        
        if not name_filled:
            print("[!] Name fill failed")
            await browser.close()
            return False
    
    # Step 8: Wait for auth code
    print("[*] Waiting for auth code...")
    for _ in range(25):
        await asyncio.sleep(2)
        
        if callback_data.get("auth_code"):
            print(f"[+] Auth code: {callback_data['auth_code'][:20]}...")
            break
        
        url = page.url
        if "code=" in url:
            qs = parse_qs(urlparse(url).query)
            if "code" in qs:
                callback_data["auth_code"] = qs["code"][0]
                break
        elif "127.0.0.1" in url or "localhost" in url:
            qs = parse_qs(urlparse(url).query)
            if "code" in qs:
                callback_data["auth_code"] = qs["code"][0]
                break
    
    if not callback_data.get("auth_code"):
        print("[!] No auth code")
        print(f"  Final URL: {page.url[:150]}")
        body = await page.evaluate("document.body.innerText")
        print(f"  Final body: {body[:200]}")
        await browser.close()
        return False
    
    # Step 9: Exchange for tokens
    print("[*] Exchanging auth code...")
    access_token, refresh_token = exchange_auth_code(
        callback_data["auth_code"], oidc["client_id"], oidc["client_secret"], oidc["code_verifier"]
    )
    
    if not refresh_token:
        print("[!] Token exchange failed")
        await browser.close()
        return False
    
    print(f"[+] Access: {access_token[:30]}...")
    print(f"[+] Refresh: {refresh_token[:30]}...")
    await browser.close()
    
    # Step 10: Import to panel
    print("[*] Importing to panel...")
    session = requests.Session()
    session.post(f"{PANEL_URL}/api/auth/login", json={"password": PANEL_PASS}, verify=False, timeout=30)
    
    import_resp = session.post(f"{PANEL_URL}/api/oauth/kiro/import", json={
        "refreshToken": refresh_token,
        "region": "us-east-1",
        "authMethod": "builder-id",
        "startUrl": "https://view.awsapps.com/start",
        "name": email,
    }, verify=False, timeout=30)
    
    result = import_resp.json()
    print(f"[+] Import: {json.dumps(result)[:300]}")
    
    if import_resp.status_code == 200:
        print(f"\n[✅] SUCCESS: {email} created + imported!")
        return True
    else:
        print(f"\n[⚠️] Created but import: {import_resp.status_code}")
        return True

async def main():
    from playwright.async_api import async_playwright
    
    server = start_callback_server()
    print("[+] Callback server on 127.0.0.1:3128")
    
    async with async_playwright() as pw:
        success = await run_flow(pw)
    
    return 0 if success else 1

if __name__ == "__main__":
    asyncio.run(main())
