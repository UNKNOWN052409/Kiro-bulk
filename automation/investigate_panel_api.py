import sys, json, time
sys.path.insert(0, r'C:\Users\Unkno\Videos\New folder\automation (2)\automation\automation')
from camoufox.sync_api import Camoufox

with Camoufox(geoip=True, humanize=True, headless=False, os='windows') as browser:
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(30000)

    # Login
    page.goto('http://localhost:20128/login', wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    
    # Login and get cookies/token
    r = page.evaluate('async () => { const resp = await fetch("/api/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: "741085209630"})}); return {ok: resp.ok, body: await resp.text()}; }')
    print(f'Login: {r["ok"]}')

    page.goto('http://localhost:20128/dashboard/providers/kiro', wait_until='domcontentloaded')
    page.wait_for_timeout(3000)

    # Try to discover the API endpoints by checking the page's JS
    # First, let's see what the device-code endpoint returns
    print('\n=== CHECKING API ENDPOINTS ===')
    
    # Check what endpoints are available
    apis = page.evaluate('''async () => {
        const results = {};
        const paths = [
            '/api/oauth/kiro/device-code',
            '/api/providers/kiro',
            '/api/providers',
            '/api/connections',
        ];
        for (const p of paths) {
            try {
                const r = await fetch(p);
                const text = await r.text();
                let summary = text.substring(0, 300);
                try { summary = JSON.stringify(JSON.parse(text), null, 2).substring(0, 500); } catch(e) {}
                results[p] = {status: r.status, body: summary};
            } catch(e) {
                results[p] = {error: e.message};
            }
        }
        return results;
    }''')
    
    for path, info in apis.items():
        print(f'\n  {path}:')
        for k, v in info.items():
            print(f'    {k}: {v}')

    # Try POST to device-code to see what parameters it expects
    print('\n=== TRYING DEVICE CODE POST ===')
    dc = page.evaluate('''async () => {
        try {
            const r = await fetch('/api/oauth/kiro/device-code', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
            return {status: r.status, body: await r.text()};
        } catch(e) {
            return {error: e.message};
        }
    }''')
    print(f'  POST /api/oauth/kiro/device-code: {json.dumps(dc, indent=2)[:500]}')

    # Try to get the device code via GET
    print('\n=== TRYING DEVICE CODE GET ===')
    dcg = page.evaluate('''async () => {
        try {
            const r = await fetch('/api/oauth/kiro/device-code');
            return {status: r.status, body: await r.text()};
        } catch(e) {
            return {error: e.message};
        }
    }''')
    print(f'  GET /api/oauth/kiro/device-code: {json.dumps(dcg, indent=2)[:500]}')

    # Look at the kiro page's next.js data for provider settings
    print('\n=== CHECKING PAGE DATA ===')
    page_data = page.evaluate('''() => {
        // Look for Next.js data
        const scripts = document.querySelectorAll('script');
        for (const s of scripts) {
            if (s.id === '__NEXT_DATA__' || (s.textContent || '').includes('__NEXT_DATA__')) {
                return s.textContent.substring(0, 3000);
            }
        }
        // Look for JSON data in script tags
        for (const s of scripts) {
            const t = (s.textContent || '').trim();
            if (t.startsWith('{') || t.startsWith('[')) {
                try {
                    const d = JSON.parse(t);
                    if (d.props || d.pageProps) return JSON.stringify(d).substring(0, 3000);
                } catch(e) {}
            }
        }
        return 'No structured data found';
    }''')
    print(f'  {page_data[:2000]}')

    input('\nPress Enter to close...')
