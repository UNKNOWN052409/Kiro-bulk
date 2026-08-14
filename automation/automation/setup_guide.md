# Gmail OAuth2 Setup Guide

This guide walks you through setting up OAuth2 for the Mail Automation project.
**Time required: ~5 minutes.**

---

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown (top-left, next to "Google Cloud")
3. Click **"New Project"**
4. Name it: `Mail Automation` (or anything you like)
5. Click **"Create"**
6. Make sure the new project is selected in the dropdown

---

## Step 2: Enable the Gmail API

1. In the left sidebar, go to **APIs & Services → Library**
   - Or direct link: https://console.cloud.google.com/apis/library
2. Search for **"Gmail API"**
3. Click on it → Click **"Enable"**

---

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
   - Or direct link: https://console.cloud.google.com/apis/credentials/consent
2. Select **"External"** → Click **"Create"**
3. Fill in the required fields:
   - **App name:** `Mail Automation`
   - **User support email:** Select your email
   - **Developer contact email:** Your email
4. Click **"Save and Continue"**
5. On the **Scopes** page → Click **"Add or Remove Scopes"**
   - Search for `https://mail.google.com/`
   - Check the box → Click **"Update"**
   - Click **"Save and Continue"**
6. On the **Test users** page → Click **"Add Users"**
   - Add: `anshika31618@gmail.com`
   - Click **"Save and Continue"**
7. Review → Click **"Back to Dashboard"**

---

## Step 4: Create OAuth2 Credentials

1. Go to **APIs & Services → Credentials**
   - Or direct link: https://console.cloud.google.com/apis/credentials
2. Click **"+ Create Credentials"** → Select **"OAuth client ID"**
3. **Application type:** Select **"Desktop app"**
4. **Name:** `Mail Automation Desktop`
5. Click **"Create"**
6. A dialog appears with your Client ID and Secret
7. Click **"Download JSON"** (⬇️ button)
8. **Rename** the downloaded file to `credentials.json`
9. **Move** it to: `d:\dowload\scrcpy-win64-v3.3.4\automation\credentials.json`

---

## Step 5: Generate Your OAuth Token

Open a terminal in the automation folder and run:

```bash
pip install -r requirements.txt
python gmail_oauth.py
```

**What happens:**
1. A browser window opens automatically
2. Sign in with `anshika31618@gmail.com`
3. You'll see a warning "Google hasn't verified this app" → Click **"Continue"**
4. Grant the requested permissions → Click **"Continue"**
5. The browser shows "The authentication flow has completed"
6. Back in the terminal, you'll see: `✅ OAuth2 authorization successful!`

A `token.json` file is created — this is your auth token. It auto-refreshes, so you only need to do this once.

---

## Step 6: Test Everything

```bash
# Test both SMTP and IMAP
python gmail_oauth.py --test

# Test sending an email
python mail_sender.py --test

# Test reading emails
python mail_reader.py --test

# Start the Flask web UI
python app.py
```

---

## Troubleshooting

### "credentials.json not found"
→ Make sure you downloaded the OAuth client JSON from Step 4 and renamed it to `credentials.json` in the automation folder.

### "Access blocked: This app's request is invalid"
→ Make sure you added `anshika31618@gmail.com` as a test user in Step 3.6.

### "Token has been expired or revoked"
→ Delete `token.json` and run `python gmail_oauth.py` again to re-authenticate.

### "SMTP/IMAP connection failed"
→ Make sure the Gmail API is enabled (Step 2) and you granted the `https://mail.google.com/` scope (Step 3.5).

---

## Security Notes

- **Never share** `credentials.json` or `token.json` publicly
- Both files are in `.gitignore` by default
- The token auto-refreshes — no manual intervention needed
- If you suspect your token is compromised, delete `token.json` and re-run `python gmail_oauth.py`
- You can revoke access anytime at: https://myaccount.google.com/permissions
