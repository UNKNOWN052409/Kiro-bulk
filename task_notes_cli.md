# Kiro CLI Token Capture - Critical Findings (Updated)

## Panel Dashboard State (from screenshot)
- Panel: 9Router Proxy v0.5.50 at https://ourproxy.sryze.cc
- Password: 7894561230
- Login URL: https://ourproxy.sryze.cc/login (password-only login, no username)
- Dashboard: https://ourproxy.sryze.cc/dashboard/providers

## Current Provider Status
- **vinay**: 22 Connected (Custom/OpenAI compatible)
- **kiro**: DISABLED (Custom provider, 0 connections)
- **n**: 9 Connected
- KILWA GROK: 1 Connected
- LONGCAT: 1 Connected
- OAuth Providers section shows: Claude Code, Antigravity, OpenAI Codex, Qoder, GitHub Copilot, Cursor IDE, Kilo Code, Cline, ClinePass, CodeBuddy, CodeBuddy CN, Kimi, Grok CLI, xAI - all "No connections"

**IMPORTANT**: There is NO separate Kiro OAuth provider visible! The "kiro" custom provider is disabled. The OAuth providers don't show a Kiro option.

## Key Discovery
The panel's earlier connections (95 total) were likely under a different provider or the dashboard has changed. The "kiro" custom provider is now DISABLED. We need to find where the Kiro OAuth connections are managed.

## Panel API
- Login: POST /api/auth/login with {"password": "7894561230"}
- Returns cookie: auth_token (JWT)
- The /api/oauth/kiro/import endpoint exists and accepts {"refreshToken": "..."}
- Returns "Refresh token is required" if field name is wrong
- Returns "Token refresh failed: Bad credentials" if refreshToken is invalid

## Kiro CLI Status
- Installed at ~/.local/bin/kiro-cli (v2.18.0)
- Login flow: kiro-cli login --use-device-flow --license free
- Shows user code, waits for browser auth
- Browser auth works: email → password → OTP → confirm
- BUT CreateToken API never returns token after browser auth completes
- The browser flow and API flow are separate OAuth paths
- kiro-cli uses fig_auth secret store (SQLite on Linux) but hasn't stored anything

## AWS Builder ID Sign-in Flow (confirmed working)
1. Open: https://view.awsapps.com/start/#/device?user_code=XXXX-XXXX
2. Enter email in input[id="resolver_input_field"]
3. Click [data-testid="test-primary-button"]
4. Enter password in input[type="password"]
5. Click button:has-text("Continue")
6. Wait for OTP email (from no-reply@login.awsapps.com, goes to Gmail Spam)
7. Enter OTP in input[placeholder="6-digit"]
8. Click Continue
9. On "Authorization requested" page, click button:has-text("Confirm and continue")
10. Done - browser redirects to view.awsapps.com

## Account: nicholas204@havenhaus.in
- Password: mGH96%cOJX#dZPM+o&
- Two-step auth: password → OTP → confirm

## Gmail OTP Extraction
- IMAP: anshika31618@gmail.com / hlcveobitfwhterw
- OTP emails go to [Gmail]/Spam folder
- From: no-reply@login.awsapps.com
- Subject: "Verify your identity"
- OTP format: 6 digits in HTML with class="code"
- Watch for false positive: 555555 (CSS artifact)

## Panel Import API Format
```
POST /api/oauth/kiro/import
Headers: Cookie: auth_token=<JWT>, Authorization: Bearer <JWT>
Body: {"refreshToken": "<aws-sso-refresh-token>"}
```

## What We Need
A valid AWS SSO OIDC refresh token from a successful CreateToken call.
The panel uses this to get access tokens and add Kiro accounts.

## Existing Scripts
- /home/ubuntu/kiro-gen/panel_add_ui.py - Panel UI device auth (worked before, added 2 accounts)
- /home/ubuntu/kiro-gen/kiro_full_login.py - Combined API+browser (CreateToken never returns)
- /home/ubuntu/kiro-gen/kiro_cli_login.py - Kiro CLI automation (CLI stuck on spinner)
- /home/ubuntu/kiro-gen/kiro_login_v2.py - Browser-mode CLI login (page stale issue)
- /home/ubuntu/kiro-gen/kiro_accounts.csv - Account database
