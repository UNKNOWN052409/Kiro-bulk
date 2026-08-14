# Kiro Builder ID Bot - Auto Starter
# Run this once and let it work autonomously

$PANEL_URL = "http://localhost:20128"
$PANEL_PASSWORD = "0S!;L5|7_X<2-|*@"
$DOMAIN = "@havenhaus.in"
$COUNTRY = "us"  # Change to 'za' for South Africa proxy
$INTERVAL = "3m"  # 3 minutes between accounts

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Kiro Builder ID Bot - Starting..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Panel:    $PANEL_URL"
Write-Host "Domain:   $DOMAIN"
Write-Host "Country:  $COUNTRY"
Write-Host "Interval: $INTERVAL seconds"
Write-Host ""
Write-Host "The bot will run continuously and add accounts automatically."
Write-Host "Press Ctrl+C to stop."
Write-Host ""

# Start the bot
python run_bot.py `
    --panel $PANEL_URL `
    --password $PANEL_PASSWORD `
    --domain $DOMAIN `
    --country $COUNTRY `
    --headless `
    --interval $INTERVAL

Write-Host ""
Write-Host "Bot stopped." -ForegroundColor Yellow
