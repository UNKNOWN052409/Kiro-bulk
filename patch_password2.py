# Fix password filling - wait for second field to appear
with open('final_flow.py', 'r') as f:
    content = f.read()

old_section = """            # Use keyboard typing to trigger React onChange properly
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
                pass_inputs.nth(0).press('Enter')"""

new_section = """            # Type in first password field
            pass_inputs.nth(0).click()
            page.keyboard.type(password, delay=50)
            print(f"[+] Password typed: {len(password)} chars")
            time.sleep(3.0)
            
            # Wait for second (confirm) field to appear
            second_field = None
            for _ in range(20):
                time.sleep(1.0)
                pass_inputs = page.locator('input[type="password"]:visible')
                cnt = pass_inputs.count()
                if cnt > 1:
                    second_field = pass_inputs.nth(1)
                    print(f"[+] Second password field appeared (total: {cnt})")
                    break
            
            if second_field:
                second_field.click()
                page.keyboard.type(password, delay=50)
                print("[+] Confirm password typed")
                time.sleep(2.0)
                second_field.press('Enter')
                print("[+] Enter pressed in confirm field")
            else:
                print(f"[!] Second field never appeared (count: {pass_inputs.count()})")
                # Try clicking Continue anyway
                pass_inputs.nth(0).press('Enter')"""

if old_section in content:
    content = content.replace(old_section, new_section)
    print("Password filling fixed")
else:
    print("ERROR: Section not found")
    import re
    # Find the actual content
    for i, line in enumerate(content.split('\n')):
        if 'pass_inputs.nth(0).click()' in line:
            print(f"Line {i}: {line[:80]}")

with open('final_flow.py', 'w') as f:
    f.write(content)
