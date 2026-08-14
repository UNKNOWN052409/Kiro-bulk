# MITM Account Creator Status

## Error: SSL WRONG_VERSION_NUMBER on view.awsapps.com
- The SOCKS5 proxy URL format `socks5://res-US:key@gw.proxyrise.com:443` causes SSL issues
- The proxy endpoint is on port 443 which is typically HTTPS, but we're using it as SOCKS5
- The IP query worked (172.58.252.86) but the redirect to view.awsapps.com fails with SSL error

## Fix needed:
1. Use `socks5h://` scheme instead of `socks5://` to force DNS resolution through proxy
2. Or use `socks4://` scheme
3. The issue is that requests library tries to do TLS handshake through the SOCKS proxy but fails
4. Need to use `socks5h` for proper SOCKS5 tunneling

## Key insight from earlier tests:
- The SOCKS5 proxy DOES work for HTTPS requests (we verified IP change)
- The issue is specifically with the redirect chain - view.awsapps.com requires a proper TLS tunnel
- Use `socks5h` scheme which tells requests to resolve DNS through the proxy too

## Proxy format that worked before:
- `socks5://res-US:key@gw.proxyrise.com:443` - worked for IP check
- But failed for view.awsapps.com redirect

## Solution:
- Add proper error handling and retry logic
- Use `socks5h` scheme
- Or use `https` proxy scheme (HTTP CONNECT) instead of socks5
