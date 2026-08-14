#!/usr/bin/env python3
"""Test OTP extraction with timestamp filtering."""
import sys
sys.path.insert(0, '/home/ubuntu/kiro-gen')
from panel_add_ui import extract_otp_gmail
import time

print("=== Test 1: Without after_timestamp (should get stale OTP) ===")
otp1 = extract_otp_gmail('ax3p0kzyk6@havenhaus.in', timeout=10)
print(f"OTP (no filter): {otp1}")

print("\n=== Test 2: With after_timestamp = now (should get None or very recent) ===")
now = time.time()
otp2 = extract_otp_gmail('ax3p0kzyk6@havenhaus.in', timeout=10, after_timestamp=now)
print(f"OTP (after={now}): {otp2}")

print("\n=== Test 3: With after_timestamp = 5 min ago (should get recent ones) ===")
five_min_ago = time.time() - 300
otp3 = extract_otp_gmail('ax3p0kzyk6@havenhaus.in', timeout=10, after_timestamp=five_min_ago)
print(f"OTP (after={five_min_ago}): {otp3}")

print("\n=== Test 4: With after_timestamp = 1 hour ago (should get any recent) ===")
one_hr_ago = time.time() - 3600
otp4 = extract_otp_gmail('ax3p0kzyk6@havenhaus.in', timeout=10, after_timestamp=one_hr_ago)
print(f"OTP (after={one_hr_ago}): {otp4}")
