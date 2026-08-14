"""Fake.legal temporary-mailbox provider with auto-fallback.

Since fake.legal server is often unreachable (dead/deprecated),
this provider automatically falls back to 1secmail.com which
requires no signup and works from any network.

Chain: fake.legal -> 1secmail.com
"""
import random
import re
import string
import time
import requests as http_requests

from .base import MailProvider


AVAILABLE_DOMAINS = ["fake.legal", "imgui.de", "pulsewebmenu.de", "gooncraft.de"]
API_BASE = "https://fake.legal/api"
SECMAIL_API = "https://www.1secmail.com/api/v1/"


def _random_username() -> str:
    """Generate a random username like fake.legal's format: turbo.falcon123"""
    adj = random.choice([
        "turbo", "swift", "cool", "mega", "super", "ultra", "neon",
        "cyber", "pixel", "storm", "flash", "blaze", "frost", "shadow",
        "echo", "nova", "zen", "flux", "vibe", "zenith", "nexus", "pulse"
    ])
    noun = random.choice([
        "falcon", "tiger", "wolf", "eagle", "hawk", "fox", "bear",
        "lion", "panda", "dragon", "phoenix", "raven", "cobra", "shark"
    ])
    num = random.randint(1, 999)
    return f"{adj}.{noun}{num}"


def _gen_random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


class FakeLegalProvider(MailProvider):
    """Fake.legal temporary mailbox provider with 1secmail fallback."""

    name = "fake_legal"
    display_name = "Fake.legal (+ 1secmail fallback)"

    def __init__(self, api_key: str = "", domain: str = "", base_url: str = ""):
        self.api_key = str(api_key).strip()
        self.domain = str(domain).strip() or random.choice(AVAILABLE_DOMAINS)
        self.api_base = str(base_url).rstrip("/") or API_BASE
        self.address = None
        self._session = http_requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        if self.api_key:
            self._session.headers["x-api-key"] = self.api_key

        # Fallback state
        self._use_fallback = False
        self._secmail_login = ""
        self._secmail_domain = ""

    def _test_fake_legal(self) -> bool:
        """Quick connectivity test for fake.legal API."""
        try:
            resp = self._session.get(f"{self.api_base}/inbox/new", params={"domain": self.domain}, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def _activate_fallback(self):
        """Switch to 1secmail fallback provider."""
        if not self._use_fallback:
            print("  [*] fake.legal unreachable, switching to 1secmail.com fallback...")
            self._use_fallback = True
        return True

    def create_mailbox(self) -> str:
        """Create a new inbox. Tries fake.legal first, falls back to 1secmail."""
        if not self._use_fallback:
            # Try fake.legal first
            try:
                url = f"{self.api_base}/inbox/new"
                params = {"domain": self.domain}
                resp = self._session.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") and data.get("address"):
                        self.address = data["address"]
                        return self.address
                elif resp.status_code == 429:
                    time.sleep(5)
                    resp = self._session.get(url, params=params, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("success") and data.get("address"):
                            self.address = data["address"]
                            return self.address
                # If not 200, fall back
            except Exception:
                pass
            self._activate_fallback()

        # Fallback: use 1secmail (no signup, no API key)
        return self._create_1secmail()

    def _create_custom(self, username: str) -> str:
        """Fallback: try custom inbox on fake.legal."""
        if self._use_fallback:
            return self._create_1secmail()
        url = f"{self.api_base}/inbox/custom"
        payload = {"username": username, "domain": self.domain}
        try:
            resp = self._session.post(url, json=payload, timeout=15, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("address"):
                    self.address = data["address"]
                    return self.address
        except Exception:
            pass
        self._activate_fallback()
        return self._create_1secmail()

    def _create_1secmail(self) -> str:
        """Create mailbox via 1secmail (no signup needed)."""
        self._secmail_login = _gen_random_string(8)
        try:
            resp = self._session.get(f"{SECMAIL_API}?action=getDomainList", timeout=10)
            if resp.status_code == 200 and isinstance(resp.json(), list) and len(resp.json()) > 0:
                self._secmail_domain = random.choice(resp.json())
            else:
                self._secmail_domain = "1secmail.com"
        except Exception:
            self._secmail_domain = "1secmail.com"

        self.address = f"{self._secmail_login}@{self._secmail_domain}"
        return self.address

    def wait_otp(self, timeout: int = 120, poll_interval: int = 3) -> str:
        """Poll for OTP code. Uses the active provider (fake.legal or 1secmail)."""
        if not self.address:
            return ""

        if self._use_fallback:
            return self._wait_1secmail_otp(timeout, poll_interval)
        return self._wait_fakelegal_otp(timeout, poll_interval)

    def _wait_fakelegal_otp(self, timeout: int, poll_interval: int) -> str:
        """Poll fake.legal inbox for OTP."""
        seen_ids = set()
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                # Check inbox
                url = f"{self.api_base}/inbox/{self.address}"
                resp = self._session.get(url, timeout=15, verify=False)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") and data.get("exists"):
                        emails = data.get("emails", [])
                        for email in emails:
                            email_id = str(email.get("id", ""))
                            if email_id in seen_ids:
                                continue
                            seen_ids.add(email_id)

                            # Get full content
                            if email_id:
                                detail_url = f"{self.api_base}/email/{email_id}"
                                detail_resp = self._session.get(detail_url, timeout=15, verify=False)
                                if detail_resp.status_code == 200:
                                    detail = detail_resp.json()
                                    if detail.get("success"):
                                        code = self._extract_code(detail.get("email", {}))
                                        if code:
                                            return code
                            # Also check summary
                            code = self._extract_code(email)
                            if code:
                                return code
            except Exception:
                pass
            time.sleep(max(0.5, poll_interval))
        return ""

    def _wait_1secmail_otp(self, timeout: int, poll_interval: int) -> str:
        """Poll 1secmail inbox for OTP."""
        seen_ids = set()
        deadline = time.time() + timeout
        login = self._secmail_login
        domain = self._secmail_domain

        while time.time() < deadline:
            try:
                resp = self._session.get(
                    f"{SECMAIL_API}?action=getMessages&login={login}&domain={domain}",
                    timeout=10
                )
                if resp.status_code == 200:
                    messages = resp.json()
                    for msg in messages:
                        msg_id = msg.get("id", "")
                        if msg_id in seen_ids:
                            continue
                        seen_ids.add(msg_id)

                        # Read full message
                        detail = self._session.get(
                            f"{SECMAIL_API}?action=readMessage&login={login}&domain={domain}&id={msg_id}",
                            timeout=10
                        )
                        if detail.status_code == 200:
                            msg_data = detail.json()
                            body = msg_data.get("textBody", "") or msg_data.get("htmlBody", "") or ""
                            subject = msg_data.get("subject", "")
                            content = f"{subject}\n{body}"
                            # Extract code
                            codes = re.findall(r'(?<!\d)(\d{6})(?!\d)', content)
                            for code in codes:
                                if code != "177010":
                                    print(f"    [+] OTP found: {code}")
                                    return code
            except Exception:
                pass
            time.sleep(max(0.5, poll_interval))
        return ""

    @staticmethod
    def _extract_code(message: dict) -> str | None:
        """Extract 6-digit OTP from email content."""
        text = message.get("text", "")
        html = message.get("html", "")
        subject = message.get("subject", "")
        content = f"{subject}\n{text}\n{html}".strip()
        if not content:
            return None

        for pattern in [
            r'(?:Verification code|Your code|Code is|code:|your code|OTP)[:\s]*(\d{6})',
            r'(\d{6})(?:\s*is\s*your|[\s\n].*valid|[\s\n].*code)',
            r'(\d{6})(?:\s*<|[\s\n])',
        ]:
            match = re.search(pattern, content, re.IGNORECASE)
            if match and match.group(1) != "177010":
                return match.group(1)

        codes = re.findall(r'(?<!\d)(\d{6})(?!\d)', content)
        for code in codes:
            if code != "177010":
                return code
        return None

    def list_domains(self) -> list[dict]:
        """Return available domains."""
        if self._use_fallback:
            return [{"id": "1secmail", "domain": self._secmail_domain}]
        return [{"id": d, "domain": d} for d in AVAILABLE_DOMAINS]

    def close(self) -> None:
        self._session.close()
