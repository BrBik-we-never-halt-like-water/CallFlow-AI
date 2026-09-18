# Daily H1 Status Check
# Run this every day to track vendor approval progress

Write-Host "=== H1 Vendor Status Check ===" -ForegroundColor Cyan
Write-Host "Date: $(Get-Date -Format 'yyyy-MM-dd')" -ForegroundColor Gray
Write-Host ""

Write-Host "Check these daily:" -ForegroundColor Yellow
Write-Host "  1. Twilio Console → Regulatory Compliance"
Write-Host "     https://console.twilio.com/us1/develop/regulatory-compliance"
Write-Host ""
Write-Host "  2. Look for:"
Write-Host "     ✓ Bundle Status: Approved (green)"
Write-Host "     ✗ Bundle Status: In Review (yellow)"
Write-Host "     ✗ Bundle Status: Rejected (red)"
Write-Host ""

$choice = Read-Host "Has KYC been approved? (y/n)"

if ($choice -eq 'y') {
    Write-Host ""
    Write-Host "✓ EXCELLENT! Proceed to provision number:" -ForegroundColor Green
    Write-Host "  1. Phone Numbers → Buy a Number"
    Write-Host "  2. Country: India (+91)"
    Write-Host "  3. Capabilities: Voice ✓"
    Write-Host "  4. Search → Select → Buy"
    Write-Host ""
    Write-Host "After provisioning, test with:" -ForegroundColor Cyan
    Write-Host "  python scripts/probe-dial.py --to +91XXXXXXXXXX"
    Write-Host ""
    Write-Host "Update ISSUES.md #209 with:" -ForegroundColor Cyan
    Write-Host "  - KYC approved: $(Get-Date -Format 'yyyy-MM-dd')"
    Write-Host "  - Number: +91..."
    Write-Host "  - Test result: [success/fail]"
} elseif ($choice -eq 'n') {
    Write-Host ""
    Write-Host "Still waiting. Status:" -ForegroundColor Yellow
    Write-Host "  - Check again tomorrow"
    Write-Host "  - If >5 days: open support ticket"
    Write-Host "  - Document any blocker in ISSUES.md #209"
} else {
    Write-Host "Invalid input. Run again." -ForegroundColor Red
}

Write-Host ""
Write-Host "Next check: $(Get-Date -Format 'yyyy-MM-dd' (Get-Date).AddDays(1))" -ForegroundColor Gray
