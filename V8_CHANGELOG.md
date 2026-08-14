# Kiro Bot V8 Changelog

## New Features
- **fake.legal Disposable Email**: Added support for 4 fake.legal domains (@fake.legal, @fakemail.net, @tmpmail.net, @fakeemail.org)
- **Anti-Ban Measures**: Random gap delays (2-8 min) between accounts; daily account limit tracker (default 500/day)
- **Panel Linking**: Integrated with 9Router-style panels (tested with rd63vjg.abc-tunnel.us)

## Bug Fixes
- **Infinite Loop Fix**: Fixed 'Continue-clicking' loop in signup flow (detects `post-name-submit` state, limits re-clicks to 2)
- **Stuck Page Detection**: Enhanced `detect_state()` to identify and recover from `view.awsapps.com` stuck pages
- **Allow Access**: Fixed panel authorization OAuth consent flow

## CLI Improvements
- Interactive CLI for Panel URL, Password, Domain selection
- Real-time progress tracking with daily limit display
