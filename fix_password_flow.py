import re

with open('final_flow.py', 'r') as f:
    content = f.read()

# Fix the password section
old_section = """        # Password creation page
        if state['onPasswordCreate']:
            print("[*] Creating password...")
            pass_inp = find_password_input(page, 0)
            if pass_inp:
                pass_inp.click()
                pass_inp.type(password, delay=50)
                print("[+] Password filled")
            
            pass_inp2 = find_password_input(page, 1)
            if pass_inp2:
                pass_inp2.click()
                pass_inp2.type(password, delay=50)
                print("[+] Confirm password filled")
            
            time.sleep(2.0)
            try:
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                print("[+] Password Continue clicked")
            except Exception:
                pass
            
            # Wait longer for Allow page after password
            state = wait_for_state(page, ['onAllow', 'onPasswordCreate', 'onErr'], max_wait=30)
            print(f"After password: onAllow={state['onAllow']}, onPasswordCreate={state['onPasswordCreate']}")"""

new_section = """        # Password creation page
        if state['onPasswordCreate']:
            print("[*] Creating password...")
            # Find all visible password inputs
            pass_inputs = page.locator('input[type="password"]:visible')
            count = pass_inputs.count()
            print(f"  Found {count} password inputs")
            
            # Fill first password input
            pass_inputs.nth(0).click()
            pass_inputs.nth(0).fill(password)
            print(f"[+] Password filled: {len(password)} chars")
            time.sleep(1.0)
            
            # Fill second password input (confirm)
            if count > 1:
                pass_inputs.nth(1).click()
                pass_inputs.nth(1).fill(password)
                print("[+] Confirm password filled")
                time.sleep(1.0)
            else:
                print("[!] Only one password input found")
            
            time.sleep(2.0)
            try:
                page.locator('button:has-text("Continue")').first.click(timeout=5000)
                print("[+] Password Continue clicked")
            except Exception:
                pass
            
            # Wait longer for Allow page after password
            state = wait_for_state(page, ['onAllow', 'onPasswordCreate', 'onErr'], max_wait=30)
            print(f"After password: onAllow={state['onAllow']}, onPasswordCreate={state['onPasswordCreate']}")"""

content = content.replace(old_section, new_section)

with open('final_flow.py', 'w') as f:
    f.write(content)

print("Password flow fixed")
