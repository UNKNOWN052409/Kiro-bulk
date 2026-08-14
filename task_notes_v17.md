# Task Notes v17 - Panel UI Structure

## Panel UI Structure (9Router Proxy v0.5.50)
The panel at https://ourproxy.sryze.cc has these sections:
- **Custom Providers** (OpenAI/Anthropic Compatible): vinay (22), kiro (Disabled), free token (Disabled), etc.
- **OAuth Providers**: Claude Code, Antigravity, OpenAI Codex, Qoder, GitHub Copilot, Cursor IDE, Kilo Code (Disabled), Cline, etc.
- **Free Tier Providers**: OpenCode Free, Gemini CLI, **Kiro AI (93 Connected)**, OpenRouter (Disabled), NVIDIA NIM (Disabled), etc.
- **API Key Providers**: Alibaba, Anthropic, Azure, Baidu, Blackbox, Cerebras, Chutes, Cohere, etc.

## Key Finding
The **Kiro AI** under "Free Tier Providers" has **93 Connected** accounts! This is where the Kiro accounts are.
The "kiro" under Custom Providers is a different provider (OpenAI/Anthropic compatible endpoint).

## The 93 Connected Accounts
These were added through the panel's device auth flow. The panel polls the AWS token endpoint after the user authorizes.

## The Issue
When we do the device auth flow through our script (not the panel's UI), the panel doesn't know to poll for the token. The panel's device auth flow probably:
1. User clicks "Add Account" on the Kiro AI card
2. Panel opens the AWS device auth page
3. User completes authorization
4. Panel's server polls the AWS token endpoint
5. Panel creates the connection

Since we're doing the browser part through our script, the panel's server doesn't know to poll.

## Solution Ideas
1. Click "Add Account" on the Kiro AI card through the panel's UI (using Playwright to interact with the panel)
2. The panel will open the device auth page - we complete it in the same browser session
3. The panel should then detect the authorization and add the account

## Working Device Auth Flow (confirmed)
1. Get device code from panel API
2. Navigate to AWS device auth page
3. Fill email (nicholas204@havenhaus.in) → Enter
4. Fill password (wbh$b999%%EbC-) → Enter
5. Extract OTP from Gmail SPAM (subject: "Verify your identity")
6. Enter OTP → Enter
7. Click "Confirm" button
8. Click "Allow" button
9. "Request approved"

## Script
/tmp/test_device_auth_v2.py - the complete working device auth script

## Panel API
- Login: POST /api/auth/login {"password": "7894561230"}
- Device code: GET /api/oauth/kiro/device-code?start_url=https://view.awsapps.com/start&region=us-east-1&auth_method=idc
- Check accounts: GET /api/providers
