# Complete API Flow (100% MITM - No Browser)

## The EXACT flow from MITM data:

### Step 1: OIDC Register (no proxy needed)
POST https://oidc.us-east-1.amazonaws.com/client/register
Body: {"clientName":"kiro-XXX","clientType":"public","scopes":[...],"grantTypes":["authorization_code","refresh_token"],"redirectUris":["http://127.0.0.1:9997/oauth/callback"],"issuerUrl":"https://view.awsapps.com/start"}
Response: {"clientId":"..."}

### Step 2: Follow redirects to get workflowStateHandle
GET OIDC authorize URL → redirects to view.awsapps.com → portal.sso → signin.aws
The WSH is found in the HTML of portal.sso response.

### Step 3: Email submit
POST https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute
Headers: Content-Type: application/json;charset=UTF-8, Origin: https://us-east-1.signin.aws, Referer: https://us-east-1.signin.aws/platform/d-9067642ac7/login?workflowStateHandle=WSH
Body: {"stepId":"get-identity-user","workflowStateHandle":"WSH","actionId":"SUBMIT","inputs":[{"input_type":"UserRequestInput","username":"email@havenhaus.in"},{"input_type":"FingerPrintRequestInput","fingerPrint":"ECdITeCs:XXX"}],"visitorId":"UUID","requestId":"UUID"}
Response: HTTP 200, returns new workflowStateHandle

### Step 4: Signup (on /api/execute, NOT /signup/api/execute)
POST https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute (SAME URL as step 3)
Headers: same as step 3
Body: {"stepId":"get-identity-user","workflowStateHandle":"WSH_FROM_STEP3","actionId":"SIGNUP","inputs":[same as step 3],"visitorId":"UUID","requestId":"UUID"}
Response: HTTP 200, returns {"requestId","workflowStateHandle","stepId":"","presentationContext","workflowResponseData"}
- The workflowStateHandle in response is the NEW WSH for /signup/api/execute
- The browser navigates to https://us-east-1.signin.aws/platform/d-9067642ac7/signup?workflowStateHandle=NEW_WSH

### Step 5: First /signup/api/execute call
POST https://us-east-1.signin.aws/platform/d-9067642ac7/signup/api/execute
Headers: same, but Referer: https://us-east-1.signin.aws/platform/d-9067642ac7/signup?workflowStateHandle=NEW_WSH
Body: {"stepId":"","workflowStateHandle":"NEW_WSH_FROM_STEP4","inputs":[{"input_type":"UserRequestInput","username":"email@havenhaus.in"},{"input_type":"FingerPrintRequestInput","fingerPrint":"ECdITeCs:XXX"}],"visitorId":"UUID","requestId":"UUID"}
Response: HTTP 200, returns new workflowStateHandle for step 6

### Step 6: Second /signup/api/execute call (stepId="start")
POST https://us-east-1.signin.aws/platform/d-9067642ac7/signup/api/execute
Headers: same as step 5
Body: {"stepId":"start","workflowStateHandle":"WSH_FROM_STEP5","inputs":[{"input_type":"UserRequestInput","username":"email@havenhaus.in"},{"input_type":"FingerPrintRequestInput","fingerPrint":"ECdITeCs:XXX"}],"visitorId":"UUID","requestId":"UUID"}
Response: HTTP 200, returns {"requestId","workflowStateHandle","stepId","presentationContext","workflowResponseData"}
- The workflowResponseData or presentationContext should contain the profile.aws.amazon.com workflowID
- The browser navigates to https://profile.aws.amazon.com/?workflowID=UUID

### Step 7: Profile API calls
All on https://profile.aws.amazon.com/
Headers: Content-Type: application/json;charset=UTF-8, Referer: https://profile.aws.amazon.com/?workflowID=UUID

7a. POST /api/get-config - Body: {}
7b. POST /api/get-app-context - Body: {"workflowID":"UUID"}
7c. POST /api/start - Body: {"workflowID":"UUID","browserData":{"attributes":{"fingerprint":"ECdITeCs:XXX","eventTimestamp":"2026-08-14T05:48:45.000Z","timeSpentOnPage":"41","eventType":"PageLoad","ubid":"118-XXX-XXXXXXX"},"cookies":{}}}
    Response: {"workflowState":"UUID",...}
7d. POST /api/send-otp - Body: {"workflowState":"UUID_FROM_START","email":"email@havenhaus.in","browserData":{"attributes":{"fingerprint":"ECdITeCs:XXX","eventTimestamp":"...","timeSpentOnPage":"5181","eventType":"PageSubmit","ubid":"118-XXX-XXXXXXX"},"cookies":{}}}
    Response: HTTP 200 with next steps (name, OTP, password)

## Key Issues Found:
1. Step 6 (signup stepId=start) returns HTTP 400 - need to check what the response body says
2. The Referer header MUST match the current page URL
3. The proxy (SOCKS5 via gw.proxyrise.com:443) works for all domains
4. Retry logic needed for proxy timeouts

## Fingerprint:
- Use static fingerprint from CloakBrowser (stored in mitm_account_creator.py)
- Slightly vary the last 20 chars for uniqueness between accounts
