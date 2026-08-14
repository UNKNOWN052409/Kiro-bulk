# Fix ERR-837 retry - wait longer and retry multiple times
with open('final_flow.py', 'r') as f:
    content = f.read()

old = """                state = wait_for_state(page, ['onOtp', 'onErr', 'onRateLimit'], max_wait=30)
                # Retry ERR-837 once
                if state['onErr']:
                    print("[!] ERR-837 - retrying...")
                    time.sleep(3)
                    inp = find_input(page)
                    if inp:
                        inp.click()
                        inp.type(name.title(), delay=100)
                        time.sleep(1.0)
                        try:
                            page.locator('button:has-text("Continue")').first.click(timeout=5000)
                        except Exception:
                            pass
                    state = wait_for_state(page, ['onOtp', 'onErr', 'onRateLimit'], max_wait=30)"""

new = """                state = wait_for_state(page, ['onOtp', 'onErr', 'onRateLimit'], max_wait=30)
                # Retry ERR-837 up to 3 times with 180s waits
                max_retries = 3
                for retry_num in range(max_retries):
                    if state['onOtp']:
                        break
                    if state['onErr'] or state['onRateLimit']:
                        wait_time = 180
                        print(f"[!] ERR-837/rateLimit - retry {retry_num+1}/{max_retries}, waiting {wait_time}s...")
                        time.sleep(wait_time)
                        # Re-check page state
                        inp = find_input(page)
                        if inp:
                            inp.click()
                            inp.type(name.title(), delay=100)
                            time.sleep(1.0)
                            try:
                                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                                print(f"[+] Name submitted (retry {retry_num+1})")
                            except Exception:
                                pass
                        state = wait_for_state(page, ['onOtp', 'onErr', 'onRateLimit'], max_wait=30)
                    else:
                        break"""

if old in content:
    content = content.replace(old, new)
    print("ERR-837 retry logic fixed")
else:
    print("ERROR: Section not found")

with open('final_flow.py', 'w') as f:
    f.write(content)
