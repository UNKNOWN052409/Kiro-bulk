"""
Analyze the captured signup flow data to understand the exact sequence.
"""

import json

with open('/home/ubuntu/kiro-gen/full_signup_flow.json', 'r') as f:
    data = json.load(f)

print(f"Total items: {len(data)}")
print()

for i, item in enumerate(data):
    item_type = item['type']
    
    if item_type == 'request':
        body = json.loads(item['post_data']) if item.get('post_data') else {}
        step_id = body.get('stepId', 'N/A')
        action = body.get('actionId', '')
        inputs_summary = []
        for inp in body.get('inputs', []):
            itype = inp.get('input_type', '')
            if itype == 'FingerPrintRequestInput':
                inputs_summary.append(f"FP")
            elif itype == 'UserRequestInput':
                inputs_summary.append(f"User:{inp.get('username', '')}")
            elif itype == 'NameRequestInput':
                inputs_summary.append(f"Name:{inp.get('name', '')}")
            elif itype == 'OtpRequestInput':
                inputs_summary.append(f"OTP:{inp.get('otp', '')}")
            elif itype == 'PasswordRequestInput':
                inputs_summary.append(f"PW:***")
            else:
                inputs_summary.append(itype.replace('RequestInput', ''))
        
        print(f"[{i:2d}] REQ  stepId={step_id:20s} action={action:8s} inputs=[{', '.join(inputs_summary)}]")
    
    else:
        body = item.get('body', {})
        status = item.get('status', 0)
        if isinstance(body, dict):
            step_id = body.get('stepId', 'N/A')
            error = body.get('message', {}).get('errorCode', '') if isinstance(body.get('message'), dict) else ''
            redirect = body.get('redirect', {})
            redirect_str = redirect.get('url', '')[:60] if redirect else ''
            wsh = body.get('workflowStateHandle', '')
            print(f"[{i:2d}] RESP status={status:3d} stepId={step_id:20s} error={error:25s} wsh={wsh[:20]:20s} redirect={redirect_str}")
        else:
            print(f"[{i:2d}] RESP status={status:3d} body={str(body)[:80]}")
