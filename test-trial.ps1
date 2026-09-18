# Trial Test Script
# Run this after getting your trial number from Twilio

# Set credentials (get from temp-twilio-credentials.txt)
$env:TWILIO_ACCOUNT_SID = "AC..."  # Your Account SID
$env:TWILIO_AUTH_TOKEN = "..."     # Your Auth Token

# Your Twilio trial number (US number works for testing)
$env:TWILIO_NUMBER = "+1737..."    # Your trial number

Write-Host "Testing Twilio → Your Verified Number" -ForegroundColor Cyan
Write-Host ""
Write-Host "From: $env:TWILIO_NUMBER" -ForegroundColor Gray
Write-Host "To: +918153083020 (your verified number)" -ForegroundColor Gray
Write-Host ""

# Test call
python scripts/probe-dial.py --to +918153083020

Write-Host ""
Write-Host "Check your phone +918153083020 - it should ring!" -ForegroundColor Green
Write-Host "Expected: You hear 'This is a CallFlow probe. You can hang up.'" -ForegroundColor Yellow
