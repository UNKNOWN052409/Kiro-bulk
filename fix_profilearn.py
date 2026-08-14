#!/usr/bin/env python3
"""For each existing @havenhaus.in Builder ID account (from fresh_kiro_accounts.csv),
do Kiro portal InitiateLogin -> Builder ID login -> capture code -> ExchangeToken (CBOR)
-> get profileArn, then patch the matching kiro_newNNN.json with profileArn.

Maps email -> kiro_newNNN.json by checking which cred file lacks profileArn and matches
the timestamp order; simpler: we try login for each, and if ExchangeToken returns a
profileArn we write it to ALL kiro_new*.json that currently lack one (profileArn is
per-Builder-ID-account-type; we verify if it works for chat later).
"""
import asyncio, sys, json, re, csv
from pathlib import Path

BOT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated")
AUT = BOT / "automation" / "automation"
sys.path.insert(0, str(AUT))
sys.path.insert(0, str(BOT / "CloakBrowser"))
import auto_kiro_register as A
import mail_reader as mr

CREDS_CSV = AUT / "fresh_kiro_accounts.csv"
GW = Path(r"C:\Users\Unkno\Videos\New folder\new try")
CREDS_DIR = GW / "kiro_creds"

CLICK_JS = """() => {
  const seen = new Set();
  document.querySelectorAll('button,a,input[type=submit]').forEach(function(b){
    const t=(b.innerText||'').trim().toLowerCase();
    if(seen.has(b)) return;
    if(/github|google|apple/.test(t)) return;
    if(/(accept|allow|continue|next|submit|verify|sign in|signin|get started|confirm|authorize)/.test(t)){
      seen.add(b); b.click();
    }
  });
}"""

def patch_profile_arn(arn):
    n = 0
    for f in CREDS_DIR.glob("kiro_new*.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if not d.get("profileArn"):
            d["profileArn"] = arn
            json.dump(d, open(f, "w", encoding="utf-8"), indent=2)
            n += 1
    print(f"[+] Patched profileArn into {n} files")
    return n

async def login_get_arn(email, password):
    kurl, kst, kcv = None, None, None
    for attempt in range(4):
        kurl, kst, kcv = A.kiro_portal_initiate("BuilderId")
        if kurl:
            break
        print(f"[!] InitiateLogin retry {attempt+1}")
        await asyncio.sleep(3)
    if not kurl:
        print("[!] InitiateLogin failed after retries"); return None
    from camoufox.async_api import AsyncCamoufox
    async with AsyncCamoufox(geoip=False, humanize=True, headless=True, args=["--no-sandbox","--disable-gpu"], os="windows") as browser:
        page = await browser.new_page()
        await page.goto(kurl, timeout=60000)
        await asyncio.sleep(5)
        # If Amazon retail signin appears, look for a 'Builder ID' link/button to switch
        async def maybe_switch_to_builderid():
            try:
                loc = page.locator('xpath=//a[contains(., "Builder ID")] | //button[contains(., "Builder ID")]')
                if await loc.count() > 0 and await loc.first.is_visible():
                    await loc.first.click(); print("[+] switched to Builder ID"); await asyncio.sleep(3); return True
            except Exception:
                pass
            return False
        # email
        for _ in range(40):
            await maybe_switch_to_builderid()
            try:
                ei = page.locator('xpath=//input[@type="email"]')
                if await ei.count()>0 and await ei.first.is_visible():
                    if (await ei.first.input_value()) != email:
                        await ei.first.fill(email); await page.evaluate(CLICK_JS); await asyncio.sleep(3)
                        print(f"[+] email filled {email}")
                        break
            except Exception: pass
            try: await page.evaluate(CLICK_JS)
            except Exception: pass
            await asyncio.sleep(2)
        # password
        for _ in range(30):
            try:
                pi = page.locator('xpath=//input[@type="password"]')
                if await pi.count()>0 and await pi.first.is_visible():
                    if (await pi.first.input_value()) != password:
                        await pi.first.fill(password); await page.evaluate(CLICK_JS); await asyncio.sleep(3)
                        print(f"[+] password filled")
                        break
            except Exception: pass
            try: await page.evaluate(CLICK_JS)
            except Exception: pass
            await asyncio.sleep(2)
        # wait for oauth callback code OR otp
        for _ in range(60):
            u = page.url
            if "app.kiro.dev/signin/oauth" in u and "code=" in u:
                code = re.search(r"code=([^&]+)", u).group(1)
                print("[+] kiro portal code captured")
                ex = A.kiro_portal_exchange("BuilderId", code, kcv, kst)
                print("[+] ExchangeToken:", ex)
                return ex.get("profile_arn") if ex else None
            # OTP
            try:
                oi = page.locator('xpath=//input[@inputmode="numeric"]')
                if await oi.count()>0 and await oi.first.is_visible():
                    otp = None
                    for _2 in range(20):
                        msgs = mr.fetch_emails(folder="INBOX", unread_only=False, limit=15, mark_as_read=False)
                        for m in msgs:
                            if "aws" in (m.get("from") or "").lower() or "verification" in (m.get("subject") or "").lower():
                                c = re.search(r"\b\d{6}\b", m.get("body") or m.get("snippet") or "")
                                if c: otp = c.group(0); break
                        if otp: break
                        await asyncio.sleep(4)
                    if otp:
                        await oi.first.fill(otp); await page.evaluate(CLICK_JS); await asyncio.sleep(3)
                        print(f"[+] OTP filled {otp}")
            except Exception: pass
            try: await page.evaluate(CLICK_JS)
            except Exception: pass
            await asyncio.sleep(2)
        print(f"[!] no callback for {email}; final url: {page.url[:90]}")
        return None

async def main():
    rows = list(csv.DictReader(open(CREDS_CSV, encoding="utf-8")))
    print(f"[*] {len(rows)} accounts to try")
    for r in rows:
        email, password = r["email"], r["password"]
        print(f"\n=== Trying {email} ===")
        arn = await login_get_arn(email, password)
        if arn:
            print(f"[SUCCESS] profileArn: {arn}")
            patch_profile_arn(arn)
            print("[*] Done — patched all missing profileArns. Stopping (one valid ARN suffices if shared).")
            return
        else:
            print("[!] no profileArn from this account, trying next")

if __name__ == "__main__":
    asyncio.run(main())
