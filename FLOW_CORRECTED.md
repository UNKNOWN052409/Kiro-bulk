# CORRECTED Complete Flow - Based on Browser Captures

## Endpoint
`POST https://us-east-1.signin.aws/platform/d-9067642ac7/api/execute`
Content-Type: application/json

## Full Sequence (captured from browser):

### Step 0: "" (empty stepId) + Fingerprint only
```json
{"stepId":"","workflowStateHandle":"{initial}","inputs":[{"input_type":"FingerPrintRequestInput","fingerPrint":"ECdITeCs:..."}],"requestId":"uuid"}
```
Response: stepId="" (empty), workflowResponseData has loginPathOptions

### Step 1: "start" + Fingerprint only
```json
{"stepId":"start","workflowStateHandle":"{from_step0}","inputs":[{"input_type":"FingerPrintRequestInput","fingerPrint":"..."}],"visitorId":"uuid","requestId":"uuid"}
```
Response: stepId="start", new workflowStateHandle

### Step 2: "get-identity-user" + SUBMIT (email)
```json
{"stepId":"get-identity-user","workflowStateHandle":"{from_step1}","actionId":"SUBMIT",
 "inputs":[
   {"input_type":"UserRequestInput","username":"email@havenhaus.in"},
   {"input_type":"ApplicationTypeRequestInput","applicationType":"SSO_INDIVIDUAL_ID"},
   {"input_type":"UserEventRequestInput","directoryId":"d-9067642ac7","userName":"email@havenhaus.in","userEvents":[{"input_type":"UserEvent","eventType":"PAGE_SUBMIT","pageName":"IDENTIFICATION","timeSpentOnPage":1229}]},
   {"input_type":"FingerPrintRequestInput","fingerPrint":"..."}
 ],
 "visitorId":"uuid","requestId":"uuid"}
```
Response: stepId="get-identity-user" (200) → then SPA sends SIGNUP

### Step 3: "get-identity-user" + SIGNUP (for new users)
```json
{"stepId":"get-identity-user","workflowStateHandle":"{same_as_step2}","actionId":"SIGNUP",
 "inputs":[
   {"input_type":"UserRequestInput","username":"email@havenhaus.in"},
   {"input_type":"FingerPrintRequestInput","fingerPrint":"..."}
 ],
 "visitorId":"uuid","requestId":"uuid"}
```
Response: 400, errorCode="ENTITY_DOES_NOT_EXIST"

### Step 4: "" (empty) + User + Fingerprint (after ENTITY_DOES_NOT_EXIST)
```json
{"stepId":"","workflowStateHandle":"{same_as_step2}","inputs":[
   {"input_type":"UserRequestInput","username":"email@havenhaus.in"},
   {"input_type":"FingerPrintRequestInput","fingerPrint":"..."}
 ],"visitorId":"uuid","requestId":"uuid"}
```
Response: stepId="user-signup", redirect.url="https://us-east-1.signin.aws/platform/d-9067642ac7/signup?workflowStateHandle={new_uuid}"

### Step 5: "start" + User + Fingerprint (on signup flow)
```json
{"stepId":"start","workflowStateHandle":"{from_step4_redirect}","inputs":[
   {"input_type":"UserRequestInput","username":"email@havenhaus.in"},
   {"input_type":"FingerPrintRequestInput","fingerPrint":"..."}
 ],"visitorId":"uuid","requestId":"uuid"}
```
Response: stepId="start", new workflowStateHandle

### Step 6: "user-signup" + SUBMIT (name)
```json
{"stepId":"user-signup","workflowStateHandle":"{from_step5}","actionId":"SUBMIT",
 "inputs":[
   {"input_type":"UserRequestInput","username":"email@havenhaus.in"},
   {"input_type":"NameRequestInput","name":"Full Name"},
   {"input_type":"ApplicationTypeRequestInput","applicationType":"SSO_INDIVIDUAL_ID"},
   {"input_type":"UserEventRequestInput","directoryId":"d-9067642ac7","userName":"email@havenhaus.in","userEvents":[{"input_type":"UserEvent","eventType":"PAGE_SUBMIT","pageName":"NAME","timeSpentOnPage":2000}]},
   {"input_type":"FingerPrintRequestInput","fingerPrint":"..."}
 ],
 "visitorId":"uuid","requestId":"uuid"}
```
Response: stepId varies (get-otp or similar), new workflowStateHandle

### Step 7: OTP step + SUBMIT
```json
{"stepId":"{otp_step_from_previous}","workflowStateHandle":"{from_step6}","actionId":"SUBMIT",
 "inputs":[
   {"input_type":"OtpRequestInput","otp":"123456"},
   {"input_type":"UserRequestInput","username":"email@havenhaus.in"},
   {"input_type":"FingerPrintRequestInput","fingerPrint":"..."}
 ],
 "visitorId":"uuid","requestId":"uuid"}
```

### Step 8: Password step + SUBMIT
```json
{"stepId":"{pw_step}","workflowStateHandle":"{from_step7}","actionId":"SUBMIT",
 "inputs":[
   {"input_type":"PasswordRequestInput","password":"strong_password"},
   {"input_type":"UserRequestInput","username":"email@havenhaus.in"},
   {"input_type":"FingerPrintRequestInput","fingerPrint":"..."}
 ],
 "visitorId":"uuid","requestId":"uuid"}
```
Response: redirect with authorization code → exchange for tokens

## Key Notes:
- The workflowStateHandle in each request is from the PREVIOUS response
- The visitorId stays the same throughout
- The requestId is unique per request
- The fingerprint is the SAME for all requests in a session
- All requests must go through the SAME residential IP (ProxyRise SOCKS5)
- Proxy format: `socks5://res-us-sid-SESSIONID:APIKEY@gw.proxyrise.com:443`
- API Key: `pgw-435fb460e7faae45f5989dcd48cf235ca35897c3e51788a1`

## Fingerprint
- Generated once via browser, saved to `/home/ubuntu/kiro-gen/fingerprint.txt`
- Format: `ECdITeCs:` + base64 data (~2000 chars)
- Reused for all accounts (it's a device identifier, not session-specific)

## Issues found:
- The name step causes ERR-837 when done without proxy (datacenter IP)
- The OTP and password steps also need residential proxy
- The complete flow must use the same ProxyRise session (sticky IP)
