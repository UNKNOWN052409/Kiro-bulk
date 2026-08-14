# CRITICAL TASK STATE - Kiro CLI Token + Panel Add

## Current Status
- Panel: 9Router at https://ourproxy.sryze.cc, Pass: 7894561230
- Kiro AI provider page: /dashboard/providers/kiro (shows 95 connections)
- Target: Add 30 new accounts (currently 95, need to reach ~125)
- 20 unique accounts available in kiro_accounts.csv

## Working Flow (CONFIRMED)
The panel_add_ui.py module's device auth flow WORKS:
1. Panel login → navigate to /dashboard/providers/kiro → Click Add → AWS Builder ID
2. Gets login URL with user_code
3. AWS sign-in: Email → "Enter your name" (fill name) → "Verify your email" (OTP) → "Confirm and continue" → Done

## Key Issues Fixed
- OTP is now extracted with after_timestamp to avoid stale OTPs
- Page state detection handles both password and OTP flows
- Confirm button matching is specific to "Authorization requested" page
- Allow page is optional (not always shown)

## Current Problem: Memory Pressure
- Sandbox has only ~3.9GB RAM, 3.3GB used
- Chrome has many renderer processes (~10+) from previous runs
- CDP connection times out at 180s due to memory pressure
- Solution: Close old Chrome tabs/pages, or use Playwright headless instead of CDP

## Files
- /home/ubuntu/kiro-gen/panel_add_ui.py - FIXED module (handle OTP flow)
- /home/ubuntu/kiro-gen/add_accounts_batch.py - Batch adder script
- /home/ubuntu/kiro-gen/kiro_accounts.csv - 20 unique accounts
- /home/ubuntu/kiro-gen/task_notes_cli.md - Earlier notes
- /home/ubuntu/kiro-gen/task_notes_cli2.md - Panel state notes

## Gmail OTP
- Email: anshika31618@gmail.com, App Pass: hlcveobitfwhterw (no spaces)
- OTP emails go to [Gmail]/Spam from no-reply@login.awsapps.com
- Subject: "Verify your identity"
- Fresh OTP only - use after_timestamp parameter

## First account in CSV
- ax3p0kzyk6@havenhaus.in / mGH96%cOJX#dZPM+o& / Ross Espinoza
- But note: the password might be wrong (this was from earlier session)
- nicholas204@havenhaus.in / wbh$b999%%EbC- / Nicholas Robinson

## To Run
```bash
cd /home/ubuntu/kiro-gen && python3 -u add_accounts_batch.py
```

## If CDP fails, use headless Playwright instead:
Change add_accounts_batch.py to use p.chromium.launch() instead of connect_over_cdp()
