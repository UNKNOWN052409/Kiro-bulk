"""
Test if the device auth works with a different approach.
Try registering the client and starting device auth, then check if the 
verification page loads correctly (without the name page issue).
"""
import boto3
from botocore.exceptions import ClientError
import json, time

def main():
    print("[*] Testing OIDC device auth flow...")
    
    client = boto3.client('sso-oidc', region_name='us-east-1')
    
    # Register client
    import uuid
    reg = client.register_client(
        clientName=f'kirocli-{uuid.uuid4().hex[:8]}',
        clientType='public'
    )
    client_id = reg['clientId']
    client_secret = reg['clientSecret']
    
    # Start device auth
    device = client.start_device_authorization(
        clientId=client_id,
        clientSecret=client_secret,
        startUrl='https://view.awsapps.com/start'
    )
    
    print(f"[*] User Code: {device['userCode']}")
    print(f"[*] Verification URI: {device['verificationUriComplete']}")
    print(f"[*] Expires in: {device['expiresIn']}s")
    
    # Save for manual browser test
    with open('/tmp/device_auth_2.json', 'w') as f:
        json.dump({
            'client_id': client_id,
            'client_secret': client_secret,
            'device_code': device['deviceCode'],
            'user_code': device['userCode'],
            'interval': device['interval'],
        }, f)
    
    print("[*] Ready for browser auth. Navigate to the verification URI.")
    print("[*] The flow is: device page -> email -> name -> OTP -> confirm -> allow")
    print("[*] If ERR-837 happens on name page, it's an AWS server issue.")

if __name__ == '__main__':
    main()
