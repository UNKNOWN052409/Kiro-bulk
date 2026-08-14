# Status V18 - Flow Works Without Proxy, ERR-837 Needs Residential Proxy

## CONFIRMED: The entire signup flow works WITHOUT proxy
1. ✅ OIDC authorize → login page
2. ✅ Email form fill + submit (Playwright native fill works)
3. ✅ Redirect to profile.aws.amazon.com (SPA navigation)
4. ✅ Name form detection + fill + submit
5. ❌ ERR-837 on name submission (datacenter IP blocked)

## The ERR-837 retry loop doesn't help - it's an IP reputation issue
- Need residential proxy for the API calls to bypass ERR-837

## ProxyRise SOCKS5 is DOWN
- Error 97: Can't complete SOCKS5 connection (error code 5 = connection refused)
- All targets refused (api.ipquery.io, example.com, aws domains)
- HTTP proxy mode returns 400
- HTTPS proxy mode returns 502
- This is a ProxyRise service outage

## browser_test.py key code patterns (working):
- Email fill: `email_input.click()` → `email_input.fill(email)` → `button.click()`
- Name fill: `page.locator('input[type="text"]').first.click()` → `.fill(name)` → Continue button
- Name form detection: `page.inner_text('body')` contains 'enter your name'
- OTP detection: broad text matching ('one-time', 'otp', 'verification', 'code')
- Gmail OTP: IMAP search for FROM amazon, regex \b(\d{6})\b

## Current blocker: ProxyRise SOCKS5 down
- Need to either wait for it to come back, or find alternative proxy
