"""
Gmail OAuth2 Authentication Module
====================================
Handles OAuth2 token management for SMTP/IMAP XOAUTH2 authentication.

First run:  Opens a browser for Google sign-in → saves token.json
After that: Automatically refreshes tokens (no interaction needed)

Usage:
    python gmail_oauth.py          # Generate/refresh token.json
    python gmail_oauth.py --test   # Test both SMTP and IMAP connections
"""

import base64
import json
import logging
import sys
import ssl
import smtplib
import imaplib
import argparse
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from mail_config import (
    GMAIL_EMAIL,
    SMTP_HOST, SMTP_PORT, SMTP_USE_TLS,
    IMAP_HOST, IMAP_PORT, IMAP_USE_SSL,
    CREDENTIALS_FILE, TOKEN_FILE, OAUTH_SCOPES,
    LOG_FILE
)

# ── Logging setup ─────────────────────────────────────────────────────────────
class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that survives OSError and UnicodeEncodeError (emoji on cp1252)."""
    def emit(self, record):
        try:
            super().emit(record)
        except (OSError, UnicodeEncodeError):
            try:
                # Retry with ASCII-safe message
                msg = self.format(record)
                stream = self.stream
                s = msg.encode('ascii', errors='replace').decode('ascii')
                stream.write(s + self.terminator)
                self.flush()
            except Exception:
                pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        SafeStreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  OAUTH2 CREDENTIAL MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def get_credentials() -> Credentials:
    """
    Load OAuth2 credentials from token.json, refreshing if expired.
    If no token exists, opens a browser for the initial consent flow.

    Returns:
        google.oauth2.credentials.Credentials — valid OAuth2 credentials
    """
    creds = None
    token_path = Path(TOKEN_FILE)
    creds_path = Path(CREDENTIALS_FILE)

    # ── Load existing token ───────────────────────────────────────────────
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), OAUTH_SCOPES)
            log.info("🔑 Loaded existing OAuth2 token")
        except Exception as e:
            log.warning(f"⚠️  Failed to load token.json: {e}")
            creds = None

    # ── Refresh or create new token ───────────────────────────────────────
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            log.info("🔄 OAuth2 token refreshed successfully")
        except Exception as e:
            log.warning(f"⚠️  Token refresh failed: {e} — will re-authenticate")
            creds = None

    if not creds or not creds.valid:
        if not creds_path.exists():
            log.error(
                f"credentials.json not found at: {creds_path.absolute()}\n"
                "   Please download it from Google Cloud Console.\n"
                "   See setup_guide.md for instructions."
            )
            raise FileNotFoundError(
                f"OAuth2 credentials file not found: {creds_path.absolute()}"
            )

        # ── Detect credential type ────────────────────────────────────────
        try:
            with open(creds_path, "r") as f:
                creds_data = json.load(f)

            # Desktop app credentials have "installed" key
            # Web app credentials have "web" key
            if "web" in creds_data and "installed" not in creds_data:
                log.error(
                    "Wrong credential type! You created 'Web application' credentials.\n"
                    "   You need 'Desktop app' credentials instead.\n"
                    "   Go to: https://console.cloud.google.com/apis/credentials\n"
                    "   1. Delete the current OAuth2 Client ID\n"
                    "   2. Create Credentials -> OAuth client ID\n"
                    "   3. Application type: 'Desktop app'\n"
                    "   4. Download the new JSON and replace credentials.json"
                )
                raise ValueError(
                    "Wrong OAuth2 credential type: 'Web application'. "
                    "Please create 'Desktop app' credentials instead. "
                    "See setup_guide.md for instructions."
                )
        except (json.JSONDecodeError, KeyError):
            pass  # Let it fail naturally during the flow

        log.info("Opening browser for Google sign-in...")
        log.info("   (If no browser opens, copy the URL from the terminal)")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(creds_path), OAUTH_SCOPES
        )

        try:
            # port=0 lets the OS pick any free port — avoids redirect_uri_mismatch
            creds = flow.run_local_server(
                port=0,
                prompt="consent",
                access_type="offline",
                open_browser=True
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "redirect_uri_mismatch" in error_msg or "redirect" in error_msg:
                log.error(
                    "redirect_uri_mismatch error! This usually means:\n"
                    "   1. You created 'Web application' instead of 'Desktop app' credentials\n"
                    "   2. Fix: Go to https://console.cloud.google.com/apis/credentials\n"
                    "   3. Delete the credential, create new one as 'Desktop app' type\n"
                    "   4. Download new credentials.json and replace the old one"
                )
            raise

        log.info("OAuth2 authorization successful!")

    # ── Save token for future use ─────────────────────────────────────────
    with open(token_path, "w") as f:
        f.write(creds.to_json())
    log.info(f"💾 Token saved to {token_path}")

    return creds


def _build_xoauth2_string(user: str, access_token: str) -> str:
    """
    Build the XOAUTH2 authentication string for SMTP/IMAP.

    Format: user=<email>\\x01auth=Bearer <token>\\x01\\x01
    """
    auth_string = f"user={user}\x01auth=Bearer {access_token}\x01\x01"
    return auth_string


# ══════════════════════════════════════════════════════════════════════════════
#  AUTHENTICATED CONNECTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_smtp_connection() -> smtplib.SMTP:
    """
    Create and return an SMTP connection authenticated via OAuth2 XOAUTH2.

    Returns:
        smtplib.SMTP — authenticated, ready-to-send connection
    """
    try:
        creds = get_credentials()
        access_token = creds.token

        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        smtp.ehlo()

        if SMTP_USE_TLS:
            context = ssl.create_default_context()
            smtp.starttls(context=context)
            smtp.ehlo()

        # XOAUTH2 authentication
        auth_string = _build_xoauth2_string(GMAIL_EMAIL, access_token)
        smtp.docmd("AUTH", "XOAUTH2 " + base64.b64encode(auth_string.encode()).decode())

        log.info(f"✅ SMTP connected as {GMAIL_EMAIL} (OAuth2)")
        return smtp

    except smtplib.SMTPAuthenticationError as e:
        log.error(f"❌ SMTP OAuth2 authentication failed: {e}")
        log.error("   Try deleting token.json and re-authenticating.")
        raise
    except ConnectionRefusedError:
        log.error(f"❌ Cannot connect to {SMTP_HOST}:{SMTP_PORT}")
        raise


def get_imap_connection() -> imaplib.IMAP4_SSL:
    """
    Create and return an IMAP connection authenticated via OAuth2 XOAUTH2.

    Returns:
        imaplib.IMAP4_SSL — authenticated IMAP connection
    """
    try:
        creds = get_credentials()
        access_token = creds.token

        if IMAP_USE_SSL:
            conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        else:
            conn = imaplib.IMAP4(IMAP_HOST, IMAP_PORT)

        # XOAUTH2 authentication
        auth_string = _build_xoauth2_string(GMAIL_EMAIL, access_token)
        conn.authenticate("XOAUTH2", lambda x: auth_string.encode())

        log.info(f"✅ IMAP connected as {GMAIL_EMAIL} (OAuth2)")
        return conn

    except imaplib.IMAP4.error as e:
        log.error(f"❌ IMAP OAuth2 login failed: {e}")
        log.error("   Try deleting token.json and re-authenticating.")
        raise
    except ConnectionRefusedError:
        log.error(f"❌ Cannot connect to {IMAP_HOST}:{IMAP_PORT}")
        raise


# ══════════════════════════════════════════════════════════════════════════════
#  CLI — Token generation & connection test
# ══════════════════════════════════════════════════════════════════════════════

def test_connections() -> bool:
    """Test both SMTP and IMAP OAuth2 connections."""
    all_ok = True

    # ── SMTP Test ─────────────────────────────────────────────────────────
    print("\n🔧 Testing SMTP connection...")
    try:
        smtp = get_smtp_connection()
        smtp.quit()
        print("✅ SMTP connection test PASSED\n")
    except Exception as e:
        print(f"❌ SMTP connection test FAILED: {e}\n")
        all_ok = False

    # ── IMAP Test ─────────────────────────────────────────────────────────
    print("🔧 Testing IMAP connection...")
    try:
        conn = get_imap_connection()
        status, folders = conn.list()
        print("📂 Available folders:")
        for folder in folders:
            print(f"   {folder.decode()}")
        conn.logout()
        print("✅ IMAP connection test PASSED\n")
    except Exception as e:
        print(f"❌ IMAP connection test FAILED: {e}\n")
        all_ok = False

    return all_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gmail OAuth2 — Generate tokens and test connections"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Test SMTP and IMAP connections after generating token"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Gmail OAuth2 Token Setup")
    print("=" * 60)

    try:
        creds = get_credentials()
        print(f"\n✅ OAuth2 token is valid for: {GMAIL_EMAIL}")
        print(f"   Token file: {Path(TOKEN_FILE).absolute()}")
        print(f"   Expires: {creds.expiry}")
    except FileNotFoundError:
        print("\n❌ Setup failed. Please follow setup_guide.md first.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ OAuth2 setup failed: {e}")
        sys.exit(1)

    if args.test:
        success = test_connections()
        sys.exit(0 if success else 1)

    print("\n💡 Run with --test to verify SMTP/IMAP connections.")
    print("   Example: python gmail_oauth.py --test")
