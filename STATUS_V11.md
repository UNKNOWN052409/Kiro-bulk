# Status V11 - Key Findings

## COMPLETE FLOW DISCOVERED (from debug_flow.py run):

The Kiro account creation flow is:
1. OIDC authorize → view.awsapps.com → signin.aws (login page with email form)
2. Email submit on signin.aws → redirects to signup page on signin.aws
3. **Signup page redirects to `profile.aws.amazon.com/?workflowID={uuid}`** ← THIS IS THE KEY
4. Name page on profile.aws.amazon.com: "Enter your name" with email shown, Name input + Continue button
5. After name submit → OTP page
6. After OTP → Password page  
7. After password → redirect to OIDC callback with auth code

## NAME PAGE DETAILS (profile.aws.amazon.com):
- URL: `https://profile.aws.amazon.com/?workflowID={uuid}#`
- Shows: "Enter your name / Email: {email} / Change / Name / [input with placeholder 'Maria José Silva'] / Continue button"
- The name input IS visible in the screenshot (step04_name_page_after_wait.png)
- There's a Continue button below the name input
- Cookie consent dialog appears (Accept/Decline buttons)

## KEY ISSUES:
1. The name input on profile.aws.amazon.com is NOT a standard `<input>` - it's likely a custom React component or shadow DOM element
2. querySelectorAll('input') only finds checkboxes/radios - the name field is something else
3. Need to use contenteditable, role="textbox", or other selectors

## WHAT WORKS:
- Browser WITHOUT proxy: SPA renders fine on datacenter IP
- Email form on signin.aws works perfectly
- The redirect chain to profile.aws.amazon.com works
- Cookie consent dialog has Accept button

## WHAT NEEDS TESTING:
- Does ERR-837 happen on profile.aws.amazon.com name submit (datacenter IP)?
- Does ERR-837 happen on OTP/password submit?
- The earlier test showed ERR-837 on send-otp through datacenter IP

## FILES:
- fill_name.py - NEW: focused script to fill name on profile.aws.amazon.com
- debug_flow.py - Debug script with screenshots
- hybrid_creator.py - Hybrid creator (browser no proxy)
- STATUS_V10.md - Previous findings
- proxy_wrapper_standalone.py - Working local HTTP→SOCKS5 proxy (port 8899)

## NEXT STEP: Run fill_name.py to test if name submission works without proxy
