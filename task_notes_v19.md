# Task Notes v19 - Kiro AI Detail Page

## Kiro AI Detail Page (/dashboard/providers/kiro)
The detail page shows:
- API endpoint configuration
- A long list of available models (kr/claude-haiku-4.5, kr/deepseek-3.2, kr/qwen3-coder-next, etc.)
- "Add Model" button at the bottom

This is the custom provider "kiro" (OpenAI/Anthropic compatible endpoint), NOT the "Kiro AI" under Free Tier Providers.

## Key Realization
The panel has TWO different Kiro providers:
1. **"kiro"** under Custom Providers - an OpenAI/Anthropic compatible endpoint (the detail page shows API config)
2. **"Kiro AI"** under Free Tier Providers - the OAuth-based Kiro provider with 93 connected accounts

The 93 accounts are under the Free Tier Providers "Kiro AI". The panel manages these through its own mechanism.

## The Real Issue
The panel's "Kiro AI" under Free Tier Providers has its own device auth flow that works ONLY through the panel's UI. When we do the device auth flow externally, the panel doesn't detect it.

## Next Steps
Let me try to interact with the "Kiro AI" card under Free Tier Providers more carefully. Maybe there's a context menu, right-click option, or a specific way to add accounts that I'm missing.

Actually, let me try hovering over the card and looking for any buttons that appear (like a "+" or "Add" button that only shows on hover).
