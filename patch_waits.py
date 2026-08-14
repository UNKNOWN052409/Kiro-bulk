# Fix the timing issues - add proper waits for page navigation
with open('final_flow.py', 'r') as f:
    content = f.read()

# 1. Fix OTP confirm wait - wait for password page to appear
old_otp = """                try:
                    page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                    print("[+] Confirm clicked")
                    time.sleep(15.0)
                except Exception:
                    pass
                
                # Wait for password creation page
                state = wait_for_state(page, ['onPasswordCreate', 'onAllow', 'onErr'], max_wait=30)"""

new_otp = """                try:
                    page.locator('button:has-text("Confirm")').first.click(timeout=5000)
                    print("[+] Confirm clicked")
                except Exception:
                    pass
                
                # Wait for password creation page (can take up to 60s)
                state = wait_for_state(page, ['onPasswordCreate', 'onAllow', 'onErr'], max_wait=60)"""

content = content.replace(old_otp, new_otp)

with open('final_flow.py', 'w') as f:
    f.write(content)

print("Updated waits")
