"""
Mail Automation - Central Configuration
========================================
Edit YOUR settings below. All other scripts import from here.
"""

# ============================================================
#  GMAIL IMAP / SMTP SERVERS
# ============================================================
IMAP_HOST    = "imap.gmail.com"
IMAP_PORT    = 993                   # IMAPS (SSL)
IMAP_USE_SSL = True

SMTP_HOST    = "smtp.gmail.com"
SMTP_PORT    = 587                   # Submission (STARTTLS)
SMTP_USE_TLS = True

# ============================================================
#  YOUR GMAIL ACCOUNT
# ============================================================
GMAIL_EMAIL = "anshika31618@gmail.com"

# ============================================================
#  OAUTH2 SETTINGS
# ============================================================
from pathlib import Path
_base_dir = Path(__file__).resolve().parent

# Download credentials.json from Google Cloud Console.
# See setup_guide.md for step-by-step instructions.
CREDENTIALS_FILE = str(_base_dir / "credentials.json")   # OAuth2 client config (from GCP)
TOKEN_FILE       = str(_base_dir / "token.json")         # Auto-generated after first sign-in

# Gmail OAuth2 scopes — full mailbox access for IMAP/SMTP
OAUTH_SCOPES = [
    "https://mail.google.com/"          # Full IMAP + SMTP access
]

# ============================================================
#  AUTOMATION SETTINGS
# ============================================================
POLL_INTERVAL_SECONDS = 30           # How often to check for new emails
INBOX_FOLDER          = "INBOX"
MAX_EMAILS_PER_POLL   = 20           # Max emails to process per cycle
LOG_FILE              = str(_base_dir / "mail_automation.log")

# Email rules — customize these for your AI automation
AUTOMATION_RULES = [
    # Example Rule
    # {
    #     "name": "Auto-reply to inquiry",
    #     "condition": {"subject_contains": "inquiry"},
    #     "action": "auto_reply",
    #     "reply_body": "Thanks for reaching out! We'll get back to you soon."
    # },
]
