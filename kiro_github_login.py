#!/usr/bin/env python3
"""Local-only: log into app.kiro.dev via GitHub IdP (NOT Builder ID -> avoids Amazon retail stall).
Capture the Kiro session cookies (RefreshToken) and any profileArn. If a real profileArn is
found, patch it into the 8 kiro_newNNN.json files / set global PROFILE_ARN.

GitHub auth happens on github.com, not Amazon, so the @havenhaus.in Amazon-retail stall is bypassed.
"""
import asyncio, sys, json, re, glob, os
from pathlib import Path

BOT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated")
AUT = BOT / "automation" / "automation"
sys.path.insert(0, str(AUT))
sys.path.insert(0, str(BOT / "CloakBrowser"))

CLICK_JS = """() => {
  const seen = new Set();
  document.querySelectorAll('button,a,input[type=submit]').forEach(function(b){
    const t=(b.innerText||'').trim().toLowerCase();
    if(/(sign in with github|continue with github|github)/.test(t)){
      seen.add(b); b.click();
    }
  });
}"""

GW = r"C:\Users\Unkno\Videos\New folder\new try"

async def login_github(email, password):
    from camoufox.async_api import AsyncCamoufox
    async with AsyncCamoufox(geoip=False, humanize=True, headless=True, args=["--no-sandbox","--disable-gpu"], os="windows") as browser:
        page = await browser.new_page()
        await page.goto("https://app.kiro.dev/signin", timeout=60000)
        await asyncio.sleep(4)
        # click GitHub
        clicked = False
        try:
            loc = page.locator('xpath=//button[contains(., "GitHub")] | //a[contains(., "GitHub")]')
            if await loc.count() > 0:
                await loc.first.click(); clicked=True; print("[+] clicked GitHub"); await asyncio.sleep(4)
        except Exception as e:
            print("[!] github click err", str(e)[:60])
        if not clicked:
            print("[!] GitHub button not found"); 
            return None
        # now on github.com login
        for _ in range(40):
            u = page.url
            if "app.kiro.dev" in u and ("oauth" in u or "code=" in u or "dashboard" in u or "/" == u[-1:]):
                print("[+] back on kiro:", u[:90]); break
            try:
                ei = page.locator('xpath=//input[@type="email"] | //input[@id="identifierId"] | //input[name="login"]')
                if await ei.count()>0 and await ei.first.is_visible():
                    if (await ei.first.input_value()) != email:
                        await ei.first.fill(email)
                        try: await page.get_by_text("Continue").first.click()
                        except: await page.evaluate(CLICK_JS)
                        await asyncio.sleep(3); print("[+] gh email filled"); break
            except Exception: pass
            await asyncio.sleep(2)
        # password
        for _ in range(30):
            u=page.url
            if "app.kiro.dev" in u: print("[+] returned to kiro:", u[:90]); break
            try:
                pi = page.locator('xpath=//input[@type="password"] | //input[name="password"]')
                if await pi.count()>0 and await pi.first.is_visible():
                    if (await pi.first.input_value()) != password:
                        await pi.first.fill(password)
                        try: await page.get_by_text("Sign in").first.click()
                        except: await page.evaluate(CLICK_JS)
                        await asyncio.sleep(4); print("[+] gh password filled"); break
            except Exception: pass
            await asyncio.sleep(2)
        # OTP / 2FA if asked
        for _ in range(30):
            u=page.url
            if "app.kiro.dev" in u: print("[+] final kiro url:", u[:90]); break
            try:
                oi = page.locator('xpath=//input[@inputmode="numeric"] | //input[contains(@autocomplete,"one-time")] | //input[@name="otp"]')
                if await oi.count()>0 and await oi.first.is_visible():
                    print("[!] 2FA/OTP requested for GitHub (cannot complete headless without code)"); break
            except Exception: pass
            await asyncio.sleep(2)
        # Handle possible Kiro 'Authorize' / 'Authorize Kiro' consent screen
        for _ in range(20):
            u=page.url
            if "app.kiro.dev" in u and ("code=" in u or "dashboard" in u or u.rstrip("/")=="https://app.kiro.dev" or u.rstrip("/")=="https://app.kiro.dev/"):
                print("[+] kiro reached:", u[:90]); break
            try:
                al = page.locator('xpath=//button[contains(., "Authorize")] | //a[contains(., "Authorize")] | //button[contains(., "Allow")] | //button[contains(., "Continue")]')
                if await al.count()>0 and await al.first.is_visible():
                    await al.first.click(); print("[+] clicked authorize/continue"); await asyncio.sleep(3)
            except Exception: pass
            try: await page.evaluate(CLICK_JS)
            except Exception: pass
            await asyncio.sleep(2)
        await asyncio.sleep(3)
        cookies = await page.context.cookies()
        return cookies

def find_profile_arn(cookies):
    for c in cookies:
        n=c["name"].lower(); v=c["value"]
        if "arn" in n or "profile" in n or "token" in n:
            if "arn:aws" in v:
                return v
    return None

async def main():
    email = sys.argv[1] if len(sys.argv)>1 else "fastwolf202@havenhaus.in"
    password = sys.argv[2] if len(sys.argv)>2 else "mhmcuQIzw1sSXmoI"
    cookies = await login_github(email, password)
    if not cookies:
        print("[!] no cookies / login failed"); return
    print(f"[+] got {len(cookies)} cookies")
    for c in cookies:
        if c["name"] in ("RefreshToken","AccessToken","SessionToken","Idp","profileArn","profile_arn") or "arn" in c["name"].lower() or "token" in c["name"].lower():
            print(f"  {c['name']} = {c['value'][:70]}{'...' if len(c['value'])>70 else ''}")
    arn = find_profile_arn(cookies)
    print("[+] profileArn found:", arn)
    if arn:
        files = sorted(glob.glob(os.path.join(GW,"kiro_creds","kiro_new*.json")))
        for f in files:
            d=json.load(open(f,encoding="utf-8"))
            d["profileArn"]=arn
            json.dump(d, open(f,"w",encoding="utf-8"), indent=2)
        print(f"[+] Patched {len(files)} account files with profileArn")
    else:
        print("[!] no profileArn in cookies (may need ExchangeToken step)")

if __name__ == "__main__":
    asyncio.run(main())
