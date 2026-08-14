# ERR-837 Bypass Solution - CRITICAL FINDING

## Problem Confirmed
- WITHOUT proxy: ERR-837 occurs after Name submission (on profile.aws.amazon.com)
- WITH proxy: profile.aws.amazon.com SPA doesn't render at all (stuck at 170 bytes)

## The Hybrid Solution
We need the proxy for the profile.aws.amazon.com page but not for the sign-in page.
The best approach is to use CDP (Chrome DevTools Protocol) to:
1. Start Chrome WITHOUT proxy
2. Navigate through sign-in page (works fine)
3. Enter email → redirects to profile.aws.amazon.com
4. The Name page renders fine WITHOUT proxy
5. Enter name → this is where ERR-837 happens
6. We need to somehow use proxy for the name submission

## Alternative: Restart browser with proxy after name page
Actually, the ERR-837 happens AFTER name submission. So:
1. Navigate to OIDC URL (no proxy needed)
2. Enter email → redirect to profile.aws.amazon.com (renders fine without proxy)
3. Enter name → click Continue
4. The page makes a POST request to AWS servers → this is where ERR-837 happens
5. If we can intercept and retry the POST through proxy, it might work

## Best Approach: Use proxy for ALL requests but fix the SPA loading issue
The real issue is that profile.aws.amazon.com takes too long to load through proxy.
Solution: Pre-warm the SPA by loading its resources separately, OR
Solution: Use a faster proxy tier, OR
Solution: Load the page without proxy, enter email/name, then submit through proxy

## Actually - The Real Fix
Looking at the flow more carefully:
- Sign-in page loads fine without proxy ✓
- profile.aws.amazon.com (Name page) loads fine without proxy ✓
- ERR-837 happens when submitting the Name (POST request) ✗

So the solution is:
1. Use NO proxy for page navigation and rendering
2. Use proxy ONLY for the specific POST requests that trigger ERR-837
3. This can be done by configuring Chrome to use proxy only for specific URLs

BUT Chrome doesn't support per-URL proxy. However, we can:
- Use `--proxy-bypass-list` to bypass proxy for certain domains
- Or use `--proxy-server` only for the domains that need it

Actually, the simplest approach: 
- Don't use proxy for sign-in page (it works fine)
- Don't use proxy for profile.aws.amazon.com rendering (it works fine)
- The ERR-837 is triggered by AWS detecting the datacenter IP during POST
- We need the proxy for the POST request

The best solution: Use the proxy for ALL requests to profile.aws.amazon.com domain only.
We can do this with `--proxy-server=socks5://127.0.0.1:10800` AND `--proxy-bypass-list="<-loopback>;*.signin.aws;*.awsapps.com;*.amazonaws.com"`

This way:
- signin.aws → no proxy (renders fine)
- awsapps.com → no proxy (renders fine)  
- amazonaws.com → no proxy (renders fine)
- profile.aws.amazon.com → USES PROXY (bypasses ERR-837)
