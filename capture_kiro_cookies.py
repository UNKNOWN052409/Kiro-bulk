#!/usr/bin/env python3
"""Local-only: log into app.kiro.dev via Builder ID using Camoufox, complete the
full login (email -> Continue -> password -> Continue -> OTP from Gmail -> Authorize),
then dump ALL cookies. Look for RefreshToken + any profileArn-bearing cookie.
If a profileArn cookie is found, it can be applied to all 8 accounts.

No API key, no proxy. Uses local Camoufox + local Gmail OAuth for OTP.
"""
import asyncio, sys, json, re
from pathlib import Path

BOT = Path(r"C:\Users\Unkno\Videos\New folder\with some fixes\kiro_bot_updated")
AUT = BOT / "automation" / "automation"
sys.path.insert(0, str(AUT))
sys.path.insert(0, str(BOT / "CloakBrowser"))
import mail_reader as mr

CLICK_JS = """() => {
  const seen = new Set();
  document.querySelectorAll('button,a,input[type=submit]').forEach(function(b){
    const t=(b.innerText||'').trim().toLowerCase();
    if(/github|google|apple/.test(t)) return;
    if(/(accept|allow|continue|next|submit|verify|sign in|signin|get started|confirm|authorize|approve)/.test(t)){
      seen.add(b); b.click();
    }
  });
}"""

async def main():
    email = sys.argv[1] if len(sys.argv) > 1 else "yxk9yg1xu0@havenhaus.in"
    password = sys.argv[2] if len(sys.argv) > 2 else "Dd@AMGL65iEjNfUz"
    from camoufox.async_api import AsyncCamoufox
    async with AsyncCamoufox(geoip=False, humanize=True, headless=True, args=["--no-sandbox","--disable-gpu"], os="windows") as browser:
        page = await browser.new_page()
        await page.goto("https://app.kiro.dev/signin", timeout=60000)
        await asyncio.sleep(4)
        # click Builder ID if present
        try:
            loc = page.locator('xpath=//button[contains(., "Builder ID")] | //a[contains(., "Builder ID")]')
            if await loc.count() > 0 and await loc.first.is_visible():
                await loc.first.click(); print("[+] clicked Builder ID"); await asyncio.sleep(3)
        except Exception: pass
        await page.goto("https://app.kiro.dev/signin", timeout=60000)
        await asyncio.sleep(3)
        # email
        for _ in range(30):
            try:
                ei = page.locator('xpath=//input[@type="email"]')
                if await ei.count()>0 and await ei.first.is_visible():
                    if (await ei.first.input_value()) != email:
                        await ei.first.fill(email); await page.evaluate(CLICK_JS); await asyncio.sleep(3); print("[+] email filled"); break
            except Exception: pass
            try: await page.evaluate(CLICK_JS)
            except Exception: pass
            await asyncio.sleep(2)
        # password
        for _ in range(25):
            try:
                pi = page.locator('xpath=//input[@type="password"]')
                if await pi.count()>0 and await pi.first.is_visible():
                    if (await pi.first.input_value()) != password:
                        await pi.first.fill(password); await page.evaluate(CLICK_JS); await asyncio.sleep(3); print("[+] password filled"); break
            except Exception: pass
            try: await page.evaluate(CLICK_JS)
            except Exception: pass
            await asyncio.sleep(2)
        # OTP or callback loop
        for _ in range(50):
            u = page.url
            if "app.kiro.dev" in u and ("code=" in u or "oauth" in u):
                print("[+] reached kiro callback:", u[:90]); break
            try:
                oi = page.locator('xpath=//input[@inputmode="numeric"] | //input[@type="text"][contains(@id,"otp")] | //input[contains(@autocomplete,"one-time")]')
                if await oi.count()>0 and await oi.first.is_visible():
                    otp = None
                    for _2 in range(15):
                        msgs = mr.fetch_emails(folder="INBOX", unread_only=False, limit=20, mark_as_read=False)
                        for m in msgs:
                            if "aws" in (m.get("from") or "").lower() or "verification" in (m.get("subject") or "").lower() or "amazon" in (m.get("from") or "").lower():
                                c = re.search(r"\b\d{6}\b", m.get("body") or m.get("snippet") or "")
                                if c: otp = c.group(0); break
                        if otp: break
                        await asyncio.sleep(4)
                    if otp:
                        await oi.first.fill(otp); await page.evaluate(CLICK_JS); print(f"[+] OTP {otp}"); await asyncio.sleep(3)
            except Exception: pass
            try: await page.evaluate(CLICK_JS)
            except Exception: pass
            await asyncio.sleep(2)
        # dump cookies
        cookies = await page.context.cookies()
        print(f"\n[+] Total cookies: {len(cookies)}")
        relevant = [c for c in cookies if c["name"] in ("RefreshToken","AccessToken","SessionToken","Idp","profileArn","ProfileArn") or "arn" in c["name"].lower() or "token" in c["name"].lower() or "profile" in c["name"].lower()]
        for c in relevant:
            val = c["value"]
            print(f"  {c['name']} = {val[:80]}{'...' if len(val)>80 else ''}")
        # also full dump of names
        print("  ALL NAMES:", [c["name"] for c in cookies])

if __name__ == "__main__":
    asyncio.run(main())
