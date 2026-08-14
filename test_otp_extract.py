"""Test OTP extraction for a new email."""
from extract_otp_v3 import extract_otp_gmail_v3

# Test with a known email that we just created
test_email = "hlh3sh6gb6@havenhaus.in"  # The one that succeeded

print(f"Testing OTP extraction for {test_email}...")
otp = extract_otp_gmail_v3(test_email)
print(f"OTP: {otp}")
