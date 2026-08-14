# Increase the wait time after password Continue click from 30s to 60s
with open('final_flow.py', 'r') as f:
    content = f.read()

# Change the password wait from 30 to 60 seconds
content = content.replace(
    "state = wait_for_state(page, ['onAllow', 'onPasswordCreate', 'onErr'], max_wait=30)",
    "state = wait_for_state(page, ['onAllow', 'onPasswordCreate', 'onErr'], max_wait=60)"
)

# Also increase the wait after OTP confirm from 8s to 15s
content = content.replace(
    """                try:
                    page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                    print("[+] Confirm clicked")
                    time.sleep(8.0)
                except Exception:
                    pass""",
    """                try:
                    page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                    print("[+] Confirm clicked")
                    time.sleep(15.0)
                except Exception:
                    pass"""
)

with open('final_flow.py', 'w') as f:
    f.write(content)

print("Updated wait times")
