# Status V19 - Complete Script Built

## Key Findings:
1. The full signup flow WORKS without proxy up to name submission
2. ERR-837 blocks name submission on datacenter IP (retry doesn't help)
3. ProxyRise SOCKS5 is DOWN (connection refused on all formats/ports)
4. playwright-stealth BREAKS the SPA rendering (don't use it)
5. Tor is installed but not routing traffic

## Working Code Patterns (verified):
- Email fill: `page.locator('input[type="email"]').first.click()` → `.fill(email)` → Continue button
- Name fill: `page.locator('input[type="text"]').first.click()` → `.fill(name)` → Continue button
- Name form detection: `page.inner_text('body')` contains 'enter your name'
- Email form detection: `page.locator('input[type="email"]').first.is_visible()`
- OTP detection: text contains 'one-time', 'otp', 'verification code', 'code'+'email'
- Password detection: text contains 'password' + 'create'/'set'
- Gmail OTP: IMAP search FROM amazon, regex \b(\d{6})\b
- Callback server: HTTP server on port 9997 captures OAuth code

## Files:
- /home/ubuntu/kiro-gen/kiro_creator.py - NEW complete production script
- /home/ubuntu/kiro-gen/browser_test.py - Working test script (confirmed flow)
- /home/ubuntu/kiro-gen/full_proxy_creator.py - Old full-proxy approach
- /home/ubuntu/kiro-gen/socks5_session.py - Persistent SOCKS5 session (works but proxy down)
- /home/ubuntu/kiro-gen/proxy_wrapper_standalone.py - HTTP-to-SOCKS5 wrapper

## Next Steps:
1. Run kiro_creator.py without proxy to verify all steps work
2. When ProxyRise comes back, add --proxy flag to bypass ERR-837
3. Scale to 30 accounts
4. Import tokens to 9Router panel (https://ourproxy.sryze.cc/dashboard/providers, user: kiro, pass: 7894561230)
