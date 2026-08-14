"""Mail.tm disposable email provider.

Free REST API at https://api.mail.tm
No authentication required for account creation.
JWT token required for inbox access.
Multiple domains available.
"""
import random
import re
import string
import time
import requests as http_requests

from .base import MailProvider


AVAILABLE_DOMAINS = ["web-library.net", "bcaoo.com", "bbitq.com", "vjuum.com", "laafd.com"]
API_BASE = "https://api.mail.tm"


def _random_username(length: int = 8) -> str:
    """Generate a random username."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _random_password(length: int = 16) -> str:
    """Generate a strong random password."""
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(random.choices(chars, k=length))


class MailTmProvider(MailProvider):
    """Mail.tm disposable email provider."""

    name = "mailtm"
    display_name = "Mail.tm"

    def __init__(self, api_key: str = "", domain: str = "", base_url: str = ""):
        self.api_key = str(api_key).strip()
        self.domain = str(domain).strip()
        self.api_base = str(base_url).rstrip("/") or API_BASE
        self.address = None
        self._token = None
        self._account_id = None
        self._password = None
        self._session = http_requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

    def _get_available_domain(self) -> str:
        """Fetch an available domain from the API."""
        try:
            resp = self._session.get(f"{self.api_base}/domains", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # Handle both list and dict response formats
                if isinstance(data, list):
                    if data:
                        return data[0]["domain"]
                elif isinstance(data, dict):
                    members = data.get("hydra:member", data.get("member", []))
                    if members:
                        return members[0]["domain"]
        except Exception:
            pass
        # Fallback to hardcoded domains
        return random.choice(AVAILABLE_DOMAINS)

    def create_mailbox(self) -> str:
        """Create a new disposable email account."""
        # Get or use specified domain
        if not self.domain:
            self.domain = self._get_available_domain()

        username = _random_username()
        password = _random_password()
        self.address = f"{username}@{self.domain}"
        self._password = password

        # Create account
        payload = {
            "address": self.address,
            "password": password,
        }

        for attempt in range(3):
            try:
                resp = self._session.post(
                    f"{self.api_base}/accounts",
                    json=payload,
                    timeout=15,
                )
                if resp.status_code == 201:
                    data = resp.json()
                    self._account_id = data.get("id", "")
                    return self.address
                elif resp.status_code == 422:
                    # Account already exists, try different username
                    username = _random_username()
                    self.address = f"{username}@{self.domain}"
                    payload["address"] = self.address
                    continue
                elif resp.status_code == 429:
                    time.sleep(2)
                    continue
                else:
                    # Try next domain
                    self.domain = self._get_available_domain()
                    self.address = f"{username}@{self.domain}"
                    payload["address"] = self.address
            except Exception as e:
                if attempt < 2:
                    time.sleep(1)
                else:
                    raise RuntimeError(f"Mail.tm create_mailbox failed: {e}")

        raise RuntimeError("Mail.tm create_mailbox failed after retries")

    def _authenticate(self) -> bool:
        """Login to get JWT token for inbox access."""
        if not self.address or not self._password:
            return False
        if self._token:
            return True

        payload = {
            "address": self.address,
            "password": self._password,
        }
        try:
            resp = self._session.post(
                f"{self.api_base}/token",
                json=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("token", "")
                self._session.headers["Authorization"] = f"Bearer {self._token}"
                return True
        except Exception:
            pass
        return False

    def wait_otp(self, timeout: int = 120, poll_interval: int = 3) -> str:
        """Poll for OTP code in the mail.tm inbox."""
        if not self.address:
            return ""

        if not self._authenticate():
            return ""

        seen_ids = set()
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                resp = self._session.get(
                    f"{self.api_base}/messages",
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Handle both list and dict response formats
                    if isinstance(data, list):
                        messages = data
                    elif isinstance(data, dict):
                        messages = data.get("hydra:member", data.get("member", []))
                    else:
                        messages = []

                    for msg in messages:
                        msg_id = str(msg.get("id", ""))
                        if msg_id in seen_ids:
                            continue
                        seen_ids.add(msg_id)

                        # Fetch full email content
                        full = self._fetch_message(msg_id)
                        code = self._extract_code(full)
                        if code:
                            return code

                        # Also check subject
                        code = self._extract_code(msg)
                        if code:
                            return code

            except Exception:
                pass
            time.sleep(max(0.5, poll_interval))

        return ""

    def _fetch_message(self, msg_id: str) -> dict:
        """Fetch full message content."""
        try:
            resp = self._session.get(
                f"{self.api_base}/messages/{msg_id}",
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}

    @staticmethod
    def _extract_code(message: dict) -> str | None:
        """Extract 6-digit OTP from email content."""
        text = message.get("text", "")
        html = message.get("html", "")
        subject = message.get("subject", "")
        from_field = str(message.get("from", {}).get("address", ""))

        content = f"{subject}\n{text}\n{html}".strip()
        if not content:
            return None

        # Try various patterns
        for pattern in [
            r'(?:Verification code|Your code|Code is|code:|your code|OTP|security code)[:\s]*(\d{6})',
            r'(\d{6})(?:\s*is\s*your|[\s\n].*valid|[\s\n].*code)',
            r'(\d{6})(?:\s*<|[\s\n])',
            r'(?:confirm|verify)\s+(?:code|number|digit)\s*(?:is|:)?\s*(\d{6})',
        ]:
            match = re.search(pattern, content, re.IGNORECASE)
            if match and match.group(1) != "177010":
                return match.group(1)

        # Fallback: find any 6-digit number
        codes = re.findall(r'(?<!\d)(\d{6})(?!\d)', content)
        for code in codes:
            if code != "177010":
                return code
        return None

    def list_domains(self) -> list[dict]:
        """Return available domains."""
        try:
            resp = self._session.get(f"{self.api_base}/domains", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # Handle both list and dict response formats
                if isinstance(data, list):
                    return [{"id": m["id"], "domain": m["domain"]} for m in data]
                elif isinstance(data, dict):
                    members = data.get("hydra:member", data.get("member", []))
                    return [{"id": m["id"], "domain": m["domain"]} for m in members]
        except Exception:
            pass
        return [{"id": d, "domain": d} for d in AVAILABLE_DOMAINS]

    def delete_account(self):
        """Delete the account (cleanup)."""
        if self._account_id and self._token:
            try:
                self._session.delete(
                    f"{self.api_base}/accounts/{self._account_id}",
                    timeout=15,
                )
            except Exception:
                pass

    def close(self) -> None:
        self._session.close()
