"""Headless Kiro Builder-ID LOGIN + token capture (adapted from kiro-register-en).

For an EXISTING @havenhaus.in AWS Builder ID account (email+password known),
drive a headless Camoufox browser through the Kiro OAuth authorize flow,
read the AWS OTP from the Gmail-forwarded @havenhaus.in mailbox, capture the
authorization code via a local callback server (127.0.0.1:3128), exchange it
for tokens, and write a gateway-compatible kiro_creds/kiro_newNNN.json.

No kiro-cli, no manual device code, no interactive browser.
Usage:
  python auto_kiro_login.py <email> <password> <index>
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import os
import secrets
import socket
import stat
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import sys as _sys
_BOT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated\automation\automation")
_sys.path.insert(0, str(_BOT))

REG_OIDC = "https://oidc.us-east-1.amazonaws.com"
REG_SCOPES = [
    "codewhisperer:completions", "codewhisperer:analysis",
    "codewhisperer:conversations", "codewhisperer:transformations",
    "codewhisperer:taskassist",
]
REG_REDIRECT_URI = "http://127.0.0.1:3128"
KIRO_SIGNIN_URL = "https://app.kiro.dev/signin"
ISSUER_URL = "https://view.awsapps.com/start/"
REG_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

GATEWAY = Path(r"C:\Users\Unkno\Videos\New folder\new try")
CREDS_DIR = GATEWAY / "kiro_creds"
CREDS_JSON = GATEWAY / "credentials.json"

auth_code_holder = {"code": ""}
signin_cb = {}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _sha1(value: str) -> str:
    return hashlib.sha1(value.encode()).hexdigest()


def read_otp(target_email, timeout=180):
    try:
        from mail_reader import fetch_emails
    except Exception as e:
        print(f"[otp] mail_reader err: {e}")
        return None
    start = time.time()
    seen = set()
    while time.time() - start < timeout:
        try:
            mails = fetch_emails(unread_only=True, limit=12, mark_as_read=False)
            for m in mails:
                if m["uid"] in seen:
                    continue
                seen.add(m["uid"])
                to = (m.get("to") or "").lower()
                subj = (m.get("subject") or "").lower()
                body = (m.get("body_text") or m.get("body_html") or "")
                if target_email.lower() in to and ("aws" in subj or "verify" in subj or "code" in subj or "otp" in subj):
                    mm = re_search(r"\b(\d{6})\b", body)
                    if mm:
                        return mm.group(1)
                if target_email.lower() in to and re_search(r"\b\d{6}\b", body):
                    return re_search(r"\b(\d{6})\b", body).group(1)
        except Exception as e:
            print(f"[otp] poll err: {e}")
        time.sleep(6)
    return None


def re_search(pat, text):
    import re
    m = re.search(pat, text)
    return m


def persist(path, client_id, client_secret, access_token, refresh_token, expires_in, email):
    CREDS_DIR.mkdir(parents=True, exist_ok=True)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    acc = {
        "refreshToken": refresh_token,
        "accessToken": access_token,
        "clientId": client_id,
        "clientSecret": client_secret,
        "region": "us-east-1",
        "startUrl": ISSUER_URL,
        "authMethod": "IdC",
        "provider": "BuilderId",
        "expiresAt": expires_at,
    }
    json.dump(acc, open(path, "w", encoding="utf-8"), indent=2)
    # append to credentials.json (gateway list format)
    existing = []
    if CREDS_JSON.exists():
        try:
            existing = json.load(open(CREDS_JSON, encoding="utf-8"))
        except Exception:
            existing = []
    if not isinstance(existing, list):
        existing = []
    if not any(str(e.get("path")) == str(path) for e in existing if isinstance(e, dict)):
        existing.append({
            "type": "json", "path": str(path), "enabled": True,
            "comment": f"Captured {email} via headless Builder ID login",
        })
        json.dump(existing, open(CREDS_JSON, "w", encoding="utf-8"), indent=2)
    print(f"[+] Wrote {path.name} + updated credentials.json ({len(existing)} entries)")


async def run(email, password, index):
    from camoufox.sync_api import Camoufox  # imported in async wrapper below
    # NOTE: we use async_playwright via Camoufox's async API
    from camoufox.async_api import AsyncCamoufox

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode()).digest())
    state_val = secrets.token_urlsafe(32)

    import requests
    reg = requests.post(f"{REG_OIDC}/client/register", json={
        "clientName": "Kiro IDE", "clientType": "public",
        "grantTypes": ["authorization_code", "refresh_token"],
        "issuerUrl": ISSUER_URL, "redirectUris": [REG_REDIRECT_URI], "scopes": REG_SCOPES,
    }, timeout=25, verify=False).json()
    if "clientId" not in reg:
        print(f"[!] OIDC register failed: {reg}")
        return 1
    client_id, client_secret = reg["clientId"], reg["clientSecret"]
    print("[+] OIDC client registered")

    signin_url = f"{KIRO_SIGNIN_URL}?" + urlencode({
        "state": state_val, "code_challenge": code_challenge,
        "code_challenge_method": "S256", "redirect_uri": REG_REDIRECT_URI,
        "redirect_from": "KiroIDE",
    })

    # local callback server
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class CB(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            c = qs.get("code", [""])[0]
            if c:
                auth_code_holder["code"] = c
                print("[+] callback got code")
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(b"<html><body>done</body></html>")
        def log_message(self, *a):
            pass
    srv = None
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 3128)); srv.close()
    except OSError:
        pass
    server = HTTPServer(("127.0.0.1", 3128), CB)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("[+] callback server on 127.0.0.1:3128")

    async with AsyncCamoufox(geoip=False, humanize=True, headless=True, os='windows') as browser:
        page = await browser.new_page()
        await page.goto(signin_url, timeout=60000)
        await asyncio.sleep(3)
        # dismiss cookie banner
        try:
            await page.evaluate("""() => { document.querySelectorAll('button').forEach(b=>{const t=(b.innerText||'').toLowerCase(); if(t.includes('accept')||t.includes('allow')||t.includes('confirm')||t.includes('agree')){b.click();}}); }""")
        except Exception:
            pass
        await asyncio.sleep(2)
        # click AWS Builder ID
        clicked = False
        for sel in ['xpath=//button[contains(text(),"AWS Builder ID")]',
                    'xpath=//button[contains(text(),"Builder ID")]',
                    'xpath=//*[@id="layout-viewport"]/div/div/div/div[2]/div/div[1]/button[3]']:
            loc = page.locator(sel)
            try:
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.click(); clicked = True; print("[+] clicked Builder ID"); break
            except Exception:
                pass
        await asyncio.sleep(4)

        # build authorize url after signin callback
        for _ in range(30):
            if signin_cb or auth_code_holder["code"]:
                break
            # capture signin callback params if any (we just need the authorize redirect)
            # Once on signin.aws / profile.aws we fill creds
            url = page.url
            if "signin.aws" in url or "profile.aws" in url:
                break
            await asyncio.sleep(1)

        # Navigate to authorize explicitly (mirrors repo)
        authorize_url = f"{REG_OIDC}/authorize?" + urlencode({
            "response_type": "code", "client_id": client_id,
            "redirect_uri": REG_REDIRECT_URI, "scopes": ",".join(REG_SCOPES),
            "state": state_val, "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        })
        await page.goto(authorize_url, timeout=60000)
        await asyncio.sleep(4)

        # STATE MACHINE: fill email -> password -> otp -> consent
        otp_done = False
        last_url = ""
        for step in range(60):
            if auth_code_holder["code"]:
                break
            url = page.url
            if url != last_url:
                print(f"[state] {url[:80]}")
                last_url = url
            # EMAIL
            try:
                ei = page.locator('xpath=//input[@type="email"]')
                if await ei.count() > 0 and await ei.first.is_visible():
                    cur = await ei.first.input_value()
                    if cur != email:
                        await ei.first.fill(email)
                        await page.evaluate("""() => { document.querySelectorAll('button').forEach(b=>{const t=(b.innerText||'').toLowerCase(); if(t.includes('continue')||t.includes('next')||t.includes('submit')||t.includes('verify')){b.click();}}); }""")
                        print("[+] email filled"); await asyncio.sleep(3)
            except Exception:
                pass
            # PASSWORD
            try:
                pi = page.locator('xpath=//input[@type="password"]')
                if await pi.count() > 0 and await pi.first.is_visible():
                    cur = await pi.first.input_value()
                    if cur != password:
                        await pi.first.fill(password)
                        await page.evaluate("""() => { document.querySelectorAll('button').forEach(b=>{const t=(b.innerText||'').toLowerCase(); if(t.includes('continue')||t.includes('next')||t.includes('submit')||t.includes('verify')||t.includes('sign')||t.includes('create')){b.click();}}); }""")
                        print("[+] password filled"); await asyncio.sleep(3)
            except Exception:
                pass
            # OTP
            if not otp_done:
                try:
                    oi = page.locator('xpath=//input[@inputmode="numeric"] | //input[@autocomplete="one-time-code"] | //input[contains(@name,"otp")] | //input[contains(@placeholder,"digit")]')
                    if await oi.count() > 0 and await oi.first.is_visible():
                        otp = read_otp(email)
                        if otp:
                            await oi.first.fill(otp)
                            await page.evaluate("""() => { document.querySelectorAll('button').forEach(b=>{const t=(b.innerText||'').toLowerCase(); if(t.includes('continue')||t.includes('verify')||t.includes('submit')){b.click();}}); }""")
                            print(f"[+] OTP {otp} filled"); otp_done = True; await asyncio.sleep(3)
                except Exception:
                    pass
            # CONSENT (authorize/allow)
            try:
                await page.evaluate("""() => { document.querySelectorAll('button').forEach(b=>{const t=(b.innerText||'').toLowerCase(); if(t.includes('allow')||t.includes('authorize')||t.includes('accept')||t.includes('confirm')||t.includes('agree')){b.click();}}); }""")
            except Exception:
                pass
            await asyncio.sleep(2)

        await browser.close()
    server.shutdown()

    code = auth_code_holder["code"]
    if not code:
        print("[!] No authorization code captured")
        return 1
    print(f"[+] authorization code captured: {code[:12]}...")

    # token exchange
    tok = requests.post(f"{REG_OIDC}/token", json={
        "clientId": client_id, "clientSecret": client_secret,
        "grantType": "authorization_code", "code": code,
        "redirectUri": REG_REDIRECT_URI, "codeVerifier": code_verifier,
    }, timeout=25, verify=False).json()
    if "accessToken" not in tok:
        print(f"[!] token exchange failed: {tok}")
        return 1
    expires_in = tok.get("expiresIn", 28800)
    fname = f"kiro_new{index.zfill(3)}.json"
    persist(CREDS_DIR / fname, client_id, client_secret, tok["accessToken"], tok["refreshToken"], expires_in, email)
    return 0


def main():
    if len(_sys.argv) < 3:
        print("usage: auto_kiro_login.py <email> <password> <index>")
        raise SystemExit(2)
    email, password = _sys.argv[1], _sys.argv[2]
    index = _sys.argv[3] if len(_sys.argv) > 3 else "0"
    # silence emoji logging
    import logging as _lg
    _lg.StreamHandler.emit = lambda self, *a, **k: None
    raise SystemExit(asyncio.run(run(email, password, index)))


if __name__ == "__main__":
    main()
