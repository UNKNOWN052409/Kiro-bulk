"""Self-contained headless Kiro Builder ID REGISTRATION + token capture.

Uses Camoufox (proven to pass AWS) directly. Mirrors the debug_flow sequence
that was verified to reach the email form. Flow:
  OIDC register -> callback server (127.0.0.1:3128) captures code
  -> Kiro signin -> click Builder ID (xpath button[3])
  -> authorize_url -> signin.aws: dismiss cookies(Accept) -> fill email -> Continue
  -> name -> password -> OTP(from Gmail) -> consent
  -> token exchange -> write gateway kiro_creds/kiro_newNNN.json + credentials.json

Usage: python auto_kiro_register.py <index>
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import os
import secrets
import socket
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
import cbor2

_BOT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated\automation\automation")
sys.path.insert(0, str(_BOT))
from gmail_oauth_provider import GmailOAuthProvider

REG_OIDC = "https://oidc.us-east-1.amazonaws.com"
REG_SCOPES = ["openid", "profile", "codewhisperer:completions", "codewhisperer:analysis",
              "codewhisperer:conversations", "codewhisperer:transformations", "codewhisperer:taskassist"]
REG_REDIRECT_URI = "http://127.0.0.1:3128"
KIRO_SIGNIN_URL = "https://app.kiro.dev/signin"
ISSUER_URL = "https://view.awsapps.com/start/"
KIRO_PORTAL = "https://app.kiro.dev"


def kiro_portal_initiate(idp="BuilderId"):
    """CBOR InitiateLogin -> returns (authorize_url, state, code_verifier)."""
    ses = requests.Session()
    ses.headers.update({
        "Content-Type": "application/cbor",
        "Accept": "application/cbor",
        "smithy-protocol": "rpc-v2-cbor",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    cv = secrets.token_urlsafe(64)
    cc = base64.urlsafe_b64encode(hashlib.sha256(cv.encode()).digest()).decode().rstrip("=")
    st = secrets.token_urlsafe(32)
    body = cbor2.dumps({
        "idp": idp,
        "redirectUri": "https://app.kiro.dev/signin/oauth",
        "codeChallenge": cc,
        "codeChallengeMethod": "S256",
        "state": st,
    })
    r = ses.post(f"{KIRO_PORTAL}/service/KiroWebPortalService/operation/InitiateLogin", data=body, timeout=25, verify=False)
    if r.status_code != 200:
        print("[!] InitiateLogin failed:", r.status_code, r.content[:160])
        return None, None, None
    d = cbor2.loads(r.content)
    return d.get("redirectUrl", ""), st, cv


def kiro_portal_exchange(idp, code, code_verifier, state):
    """CBOR ExchangeToken -> returns dict with profileArn, refresh_token, access_token."""
    ses = requests.Session()
    ses.headers.update({
        "Content-Type": "application/cbor",
        "Accept": "application/cbor",
        "smithy-protocol": "rpc-v2-cbor",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    body = cbor2.dumps({
        "idp": idp,
        "code": code,
        "codeVerifier": code_verifier,
        "redirectUri": "https://app.kiro.dev/signin/oauth",
        "state": state,
    })
    r = ses.post(f"{KIRO_PORTAL}/service/KiroWebPortalService/operation/ExchangeToken", data=body, timeout=25, verify=False)
    cookies = {}
    for ch in r.headers.get("Set-Cookie", "").split(","):
        if "=" in ch:
            parts = ch.strip().split(";")[0]
            if "=" in parts:
                n, v = parts.split("=", 1)
                cookies[n.strip()] = v.strip()
    if r.status_code != 200:
        print("[!] ExchangeToken failed:", r.status_code, r.content[:160])
        return None
    d = cbor2.loads(r.content)
    return {
        "profile_arn": d.get("profileArn"),
        "access_token": d.get("accessToken") or cookies.get("AccessToken"),
        "refresh_token": cookies.get("RefreshToken") or cookies.get("SessionToken"),
        "csrf_token": d.get("csrfToken"),
    }


GATEWAY = Path(r"C:\Users\Unkno\Videos\New folder\new try")
CREDS_DIR = GATEWAY / "kiro_creds"
CREDS_JSON = GATEWAY / "credentials.json"

auth_code = {"v": ""}

# Matches: accept/allow/continue/next/submit/verify/get started/sign up/sign in/
# create/get /confirm/authorize/agree
CLICK_JS = (
    "() => { document.querySelectorAll('button').forEach(function(b){"
    "var t=(b.innerText||'').toLowerCase();"
    "if(t.indexOf('with google')>=0||t.indexOf('with apple')>=0"
    "||t.indexOf('with github')>=0||t.indexOf('with amazon')>=0) return;"
    "if(t==='continue'||t==='create'||t==='get started'||t==='accept'"
    "||t==='allow'||t.indexOf('allow access')>=0||t==='verify'||t==='confirm'||t==='authorize'"
    "||t==='agree'||t==='next'||t==='submit'||t==='sign up'"
    "||t==='sign in'||t.indexOf('get started')>=0){b.click();}}); }"
)


def _b64url(d):
    return base64.urlsafe_b64encode(d).decode().rstrip("=")


async def run(index):
    from camoufox.async_api import AsyncCamoufox

    prov = GmailOAuthProvider(domain="havenhaus.in", length=10)
    email = prov.create_mailbox()
    password = "".join(secrets.choice("!@#$%ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789") for _ in range(16))
    full_name = "User Name"
    print(f"[*] email={email} name={full_name}")

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode()).digest())
    state_val = secrets.token_urlsafe(32)

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
        "code_challenge_method": "S256", "redirect_uri": REG_REDIRECT_URI, "redirect_from": "KiroIDE"})

    class CB(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            c = qs.get("code", [""])[0]
            if c:
                auth_code["v"] = c
                print("[+] callback got code")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>done</body></html>")
        def log_message(self, *a):
            pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 3128))
        s.close()
    except OSError:
        pass
    server = HTTPServer(("127.0.0.1", 3128), CB)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("[+] callback server on 127.0.0.1:3128")

    captured = {"profile_arn": ""}
    _apilog = open(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated\api_dump.txt", "a", encoding="utf-8")
    def _capture(resp):
        try:
            u = resp.url
            if ("api" in u or "profile.aws" in u) and resp.status < 400:
                try:
                    body = resp.text or ""
                except Exception:
                    body = ""
                if "arn:aws" in body or "profileArn" in body or "identity" in body.lower() or "create-identity" in u:
                    print("[dbg-api]", u[:80], "::", body[:260], flush=True)
                    _apilog.write("URL: " + u + "\nBODY: " + body[:800] + "\n=== \n")
                    _apilog.flush()
                import re as _re
                m = _re.search(r"arn:aws:[a-zA-Z0-9_:/-]+", body)
                if m and not captured["profile_arn"]:
                    captured["profile_arn"] = m.group(0)
                    print("[+] captured profileArn:", m.group(0)[:70], flush=True)
        except Exception:
            pass
    async with AsyncCamoufox(geoip=False, humanize=True, headless=True, args=["--no-sandbox", "--disable-gpu"], os="windows") as browser:
        page = await browser.new_page()
        try:
            page.on("response", _capture)
        except Exception:
            pass
        await page.goto(signin_url, timeout=60000)
        await asyncio.sleep(6)
        try:
            await page.evaluate(CLICK_JS)
        except Exception:
            pass
        await asyncio.sleep(3)
        # Select Builder ID. Kiro may either show the button (click it) OR
        # auto-redirect to our callback with login_option=builderid (already selected).
        clicked = False
        for attempt in range(15):
            await asyncio.sleep(2)
            if "login_option=builderid" in page.url:
                clicked = True
                print("[+] builderid already selected (callback redirect)")
                break
            try:
                await page.evaluate(CLICK_JS)
            except Exception:
                pass
            sels = ['xpath=//*[@id="layout-viewport"]/div/div/div/div[2]/div/div[1]/button[3]',
                    'xpath=//button[contains(normalize-space(.),"Builder ID")]',
                    'xpath=//button[contains(.,"Builder ID")]',
                    'xpath=//button[contains(.,"builder")]']
            for sel in sels:
                loc = page.locator(sel)
                try:
                    if await loc.count() > 0 and await loc.first.is_visible():
                        await loc.first.click()
                        clicked = True
                        print("[+] clicked Builder ID")
                        break
                except Exception:
                    pass
            if clicked:
                break
        # ensure we are past the Kiro signin (on AWS authorize)
        if "login_option=builderid" in page.url or "signin" in page.url:
            await asyncio.sleep(2)
        if not clicked:
            try:
                btns = await page.evaluate("() => Array.from(document.querySelectorAll('button')).map(function(b){return (b.innerText||'').trim().slice(0,40);})")
                print("[debug] signin buttons:", btns)
                print("[debug] url:", page.url[:80])
            except Exception as e:
                print("[debug] err:", e)
            print("[!] Builder ID button not found")
            await browser.close()
            server.shutdown()
            return 1
        await asyncio.sleep(5)

        authorize_url = f"{REG_OIDC}/authorize?" + urlencode({
            "response_type": "code", "client_id": client_id, "redirect_uri": REG_REDIRECT_URI,
            "scopes": ",".join(REG_SCOPES), "state": state_val,
            "code_challenge": code_challenge, "code_challenge_method": "S256"})
        await page.goto(authorize_url, timeout=60000)
        await asyncio.sleep(5)
        # Dump full HTML once (profile.aws embeds builder identity / account id)
        try:
            _h = await page.content()
            open(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated\page_html.txt", "w", encoding="utf-8").write(_h)
        except Exception:
            pass

        otp_done = False
        for step in range(90):
            if auth_code["v"]:
                break
            if step < 3 or step % 15 == 0:
                print(f"[dbg] step={step} url={page.url[:75]}", flush=True)
            try:
                await page.evaluate(CLICK_JS)
            except Exception:
                pass
            await asyncio.sleep(1)
            # EMAIL
            try:
                ei = page.locator('xpath=//input[@type="email"]')
                if await ei.count() > 0 and await ei.first.is_visible():
                    cur = await ei.first.input_value()
                    if cur != email:
                        await ei.first.fill(email)
                        await page.evaluate(CLICK_JS)
                        print(f"[+] email filled; url={page.url[:60]}")
                        await asyncio.sleep(3)
            except Exception:
                pass
            # NAME (placeholder like Silva / name field)
            try:
                ni = page.locator('xpath=//input[contains(@placeholder,"Silva")] | //input[contains(@placeholder,"name")] | //input[contains(@id,"name")] | //input[contains(@name,"name")]')
                if await ni.count() > 0 and await ni.first.is_visible():
                    cur = await ni.first.input_value()
                    if cur != full_name:
                        await ni.first.fill(full_name)
                        await page.evaluate(CLICK_JS)
                        print("[+] name filled")
                        await asyncio.sleep(3)
            except Exception:
                pass
            # PASSWORD (fill ALL password fields: Enter + Re-enter)
            try:
                pws = page.locator('xpath=//input[@type="password"] | //input[contains(@placeholder,"password")] | //input[contains(@placeholder,"Password")]')
                if await pws.count() > 0:
                    need = False
                    for k in range(await pws.count()):
                        el = pws.nth(k)
                        if await el.is_visible():
                            cv = await el.input_value()
                            if cv != password:
                                await el.fill(password)
                                need = True
                    if need:
                        # check any terms/agreement checkbox (not awsccc cookies)
                        try:
                            cbs = page.locator('xpath=//input[@type="checkbox" and not(starts-with(@id,"awsccc")) and not(contains(@name,"awsccc"))]')
                            for k in range(await cbs.count()):
                                cb = cbs.nth(k)
                                if await cb.is_visible() and not await cb.is_checked():
                                    await cb.check()
                        except Exception:
                            pass
                        await page.evaluate(CLICK_JS)
                        print("[+] password(s) filled + terms checked")
                        await asyncio.sleep(3)
            except Exception:
                pass
            # OTP
            if not otp_done:
                try:
                    oi = page.locator('xpath=//input[@inputmode="numeric"] | //input[@autocomplete="one-time-code"] | //input[contains(@name,"otp")] | //input[contains(@placeholder,"digit")]')
                    if await oi.count() > 0 and await oi.first.is_visible():
                        otp = prov.wait_otp(timeout=120, poll_interval=4)
                        if otp:
                            await oi.first.fill(otp)
                            await page.evaluate(CLICK_JS)
                            print(f"[+] OTP {otp} filled")
                            otp_done = True
                            await asyncio.sleep(3)
                except Exception:
                    pass
            if step in (5, 10, 20, 40):
                try:
                    dbg = await page.evaluate("() => ({btns: Array.from(document.querySelectorAll('button')).map(b=>(b.innerText||'').trim().slice(0,40)), inputs: Array.from(document.querySelectorAll('input')).map(i=>i.type+':'+(i.placeholder||i.name||i.id)+'=LEN'+((i.value||'').length)), text: document.body.innerText.slice(0,160)})")
                    print(f"[dbg] step={step} btns={dbg['btns']}", flush=True)
                    print(f"[dbg] step={step} inputs={dbg['inputs']}", flush=True)
                    print(f"[dbg] step={step} text={dbg['text']!r}", flush=True)
                except Exception as e:
                    print("[dbg] err", e, flush=True)
            await asyncio.sleep(1)
        await browser.close()
    server.shutdown()

    code = auth_code["v"]
    if not code:
        print("[!] No authorization code captured")
        return 1
    print(f"[+] authorization code captured: {code[:12]}...")

    # Try to grab profileArn from the current page HTML (profile.aws embeds identity)
    try:
        _html = await page.content()
        import re as _re2
        _m = _re2.search(r"arn:aws:[a-zA-Z0-9_:/-]+", _html)
        if _m and not captured.get("profile_arn"):
            captured["profile_arn"] = _m.group(0)
            print("[+] profileArn from page HTML:", _m.group(0)[:70], flush=True)
    except Exception as _he:
        print("[dbg] page content err:", _he, flush=True)

    tok = requests.post(f"{REG_OIDC}/token", json={
        "clientId": client_id, "clientSecret": client_secret,
        "grantType": "authorization_code", "code": code,
        "redirectUri": REG_REDIRECT_URI, "codeVerifier": code_verifier,
    }, timeout=25, verify=False).json()
    if "accessToken" not in tok:
        print(f"[!] token exchange failed: {tok}")
        return 1
    print("[dbg] token keys:", list(tok.keys()), flush=True)
    expires_in = tok.get("expiresIn", 28800)

    # --- Kiro portal flow: get profileArn via CBOR ExchangeToken ---
    # The browser is already logged into AWS Builder ID. Use Kiro's portal
    # InitiateLogin (which returns the AWS authorize URL for Kiro's own SSO app)
    # then capture the code from app.kiro.dev/signin/oauth and exchange it.
    if not captured.get("profile_arn"):
        try:
            _kurl, _kst, _kcv = kiro_portal_initiate("BuilderId")
            if _kurl:
                print("[+] Kiro portal InitiateLogin ok, navigating...", flush=True)
                await page.goto(_kurl, timeout=60000)
                await asyncio.sleep(4)
                _kcode = ""
                for _ in range(20):
                    _u = page.url
                    if "app.kiro.dev/signin/oauth" in _u and "code=" in _u:
                        _kcode = urlparse(_u).query
                        _kcode = parse_qs(_kcode).get("code", [""])[0]
                        break
                    await asyncio.sleep(2)
                if _kcode:
                    print("[+] Kiro portal code captured", flush=True)
                    _ex = kiro_portal_exchange("BuilderId", _kcode, _kcv, _kst)
                    if _ex and _ex.get("profile_arn"):
                        captured["profile_arn"] = _ex["profile_arn"]
                        print("[+] profileArn from ExchangeToken:", _ex["profile_arn"][:70], flush=True)
                    elif _ex:
                        print("[dbg] ExchangeToken no profileArn:", _ex)
                else:
                    print("[!] Kiro portal code not captured (url:", page.url[:80], ")", flush=True)
        except Exception as _pe:
            print("[dbg] Kiro portal flow err:", _pe, flush=True)

    # Decode id_token (JWT) to extract AWS Builder ID identity / profile ARN
    import base64 as _b64
    idt = tok.get("idToken") or tok.get("id_token")
    if idt and not captured.get("profile_arn"):
        try:
            _pt = idt.split(".")[1]
            _pt += "=" * (-len(_pt) % 4)
            _claims = json.loads(_b64.urlsafe_b64decode(_pt))
            for _k, _v in _claims.items():
                _s = str(_v)
                if "arn:aws" in _s:
                    captured["profile_arn"] = _s
                    print("[+] profileArn from id_token:", _s[:70], flush=True)
                    break
            if not captured.get("profile_arn"):
                print("[dbg] id_token claims:", list(_claims.keys()))
        except Exception as _e:
            print("[dbg] id_token decode err:", _e)
    fname = f"kiro_new{str(index).zfill(3)}.json"
    CREDS_DIR.mkdir(parents=True, exist_ok=True)
    fpath = CREDS_DIR / fname
    acc = {"refreshToken": tok["refreshToken"], "accessToken": tok["accessToken"],
           "clientId": client_id, "clientSecret": client_secret, "region": "us-east-1",
           "startUrl": ISSUER_URL, "authMethod": "IdC", "provider": "BuilderId",
           "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).strftime("%Y-%m-%dT%H:%M:%S.000Z")}
    if captured.get("profile_arn"):
        acc["profileArn"] = captured["profile_arn"]
    json.dump(acc, open(fpath, "w", encoding="utf-8"), indent=2)
    existing = []
    if CREDS_JSON.exists():
        try:
            existing = json.load(open(CREDS_JSON, encoding="utf-8"))
        except Exception:
            existing = []
    if not isinstance(existing, list):
        existing = []
    if not any(str(e.get("path")) == str(fpath) for e in existing if isinstance(e, dict)):
        existing.append({"type": "json", "path": str(fpath), "enabled": True, "comment": f"Captured {email} (headless register)"})
        json.dump(existing, open(CREDS_JSON, "w", encoding="utf-8"), indent=2)
    print(f"[+] Wrote {fname} + credentials.json ({len(existing)} entries)")
    import csv
    csvp = _BOT / "fresh_kiro_accounts.csv"
    fe = csvp.exists()
    with open(csvp, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not fe:
            w.writerow(["email", "password", "ts"])
        w.writerow([email, password, time.strftime("%Y-%m-%d %H:%M:%S")])
    return 0


def main():
    import logging as _lg
    for n in list(_lg.root.manager.loggerDict):
        _lg.getLogger(n).disabled = True
    _lg.StreamHandler.emit = lambda self, *a, **k: None
    idx = sys.argv[1] if len(sys.argv) > 1 else "0"
    raise SystemExit(asyncio.run(run(idx)))


if __name__ == "__main__":
    main()
