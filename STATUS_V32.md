# Kiro Account Creator - Status V32

## Current State
- proxy_wrapper_standalone.py (v5) WORKS: HTTP local proxy → HTTPS to ProxyRise with sticky sessions
  - All requests get same US residential IP (e.g., 173.170.51.88, 50.124.236.4, 47.203.211.142)
  - Run: `python3 proxy_wrapper_standalone.py --port 8899 --session res-us`

## kiro_final.py - Current Architecture
1. OIDC register via curl_cffi + HTTP proxy 8899
2. Browser navigate to OIDC authorize URL (wait_until='load')
3. JS redirect to signin.aws with workflowStateHandle
4. Steps 3-4: api_eval() on SIGNIN_BASE (us-east-1.signin.aws/platform/d-9067642ac7)
   - Init (stepId=''), Load email form (stepId='start'), Submit email (SIGNUP action)
5. Steps 5+: Navigate to profile.aws.amazon.com, then api_eval() there
   - Init, Load name form, Submit name, Send OTP, Verify OTP, Set password
6. Token exchange via curl_cffi

## BUG FOUND
- Step 4b calls `api_eval(SIGNIN_BASE, ...)` missing `page` as first arg
- Fix: change to `api_eval(page, SIGNIN_BASE, ...)`

## Key Findings
- OIDC authorize redirects to view.awsapps.com/start, then JS redirects to signin.aws
- Email submit uses action_id='SIGNUP' (not SUBMIT) with UserRequestInput
- Redirect from email submit: stepId='user-signup', new workflowStateHandle
- Signup flow uses profile.aws.amazon.com (NOT signin.aws/signup)
- page.evaluate() fetch with credentials:include works for same-origin
- 'Execution context destroyed' errors happen when page navigates during fetch
- Retries with increasing wait times help

## API Flow (confirmed working for steps 1-4a)
- Init: stepId='', inputs=[FingerPrintRequestInput] → step='start'
- Load email form: stepId='start', inputs=[FingerPrintRequestInput] → step='get-identity-user', actions=['SUBMIT','SIGNUP','CHOOSE_DIFFERENT_LOGIN_PATH']
- Submit email: stepId='get-identity-user', SIGNUP action, inputs=[FingerPrintRequestInput, UserRequestInput(identity=email)] → step='user-signup', redirect to profile.aws.amazon.com

## Remaining to fix
1. Fix api_eval call for step 4b (missing page arg)
2. Fix signup flow on profile.aws.amazon.com (currently returns status 0)
3. OTP extraction from Gmail works (anshika31618@gmail.com)
4. Token exchange works (curl_cffi)
5. Import to 9Router panel (https://ourproxy.sryze.cc/dashboard/providers, pass: 7894561230)

## Gmail OTP credentials
- Email: anshika31618@gmail.com
- App password: hlcv eobi tfwh terw

## ProxyRise
- API Key: pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1
- Endpoint: gw.proxyrise.com:443
- HTTPS mode: https://res-us:{API_KEY}@gw.proxyrise.com:443
- Sticky session: res-us-sid-{random_number}
