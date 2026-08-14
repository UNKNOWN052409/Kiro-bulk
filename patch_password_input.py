# Fix password input method - use keyboard typing and press Enter in second field
with open('final_flow.py', 'r') as f:
    content = f.read()

old_section = """        # Password creation page
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
            state = wait_for_state(page, ['onAllow', 'onPasswordCreate', 'onErr'], max_wait=60)
            print(f"After password: onAllow={state['onAllow']}, onPasswordCreate={state['onPasswordCreate']}")"""

new_section = """        # Password creation page
        if state['onPasswordCreate']:
            print("[*] Creating password...")
            # Find all visible password inputs
            pass_inputs = page.locator('input[type="password"]:visible')
            count = pass_inputs.count()
            print(f"  Found {count} password inputs")
            
            # Use keyboard typing to trigger React onChange properly
            # Click first password input and type
            pass_inputs.nth(0).click()
            page.keyboard.type(password, delay=50)
            print(f"[+] Password typed: {len(password)} chars")
            time.sleep(2.0)
            
            # Click second password input and type
            if count > 1:
                pass_inputs.nth(1).click()
                page.keyboard.type(password, delay=50)
                print("[+] Confirm password typed")
                time.sleep(2.0)
                
                # Press Enter in the confirm field to submit
                pass_inputs.nth(1).press('Enter')
                print("[+] Enter pressed in confirm field")
            else:
                print("[!] Only one password input found")
                pass_inputs.nth(0).press('Enter')
            
            # Wait longer for Allow page after password
            state = wait_for_state(page, ['onAllow', 'onPasswordCreate', 'onErr'], max_wait=60)
            print(f"After password: onAllow={state['onAllow']}, onPasswordCreate={state['onPasswordCreate']}")
            if not state['onAllow']:
                # Try clicking Continue button as fallback
                print("[*] Trying Continue button...")
                try:
                    page.locator('button:has-text("Continue")').first.click(timeout=5000)
                    time.sleep(5.0)
                except Exception:
                    pass
                state = wait_for_state(page, ['onAllow', 'onPasswordCreate', 'onErr'], max_wait=30)
                print(f"After button click: onAllow={state['onAllow']}")"""

if old_section in content:
    content = content.replace(old_section, new_section)
    print("Password section updated successfully")
else:
    print("ERROR: Could not find old section")

with open('final_flow.py', 'w') as f:
    f.write(content)
