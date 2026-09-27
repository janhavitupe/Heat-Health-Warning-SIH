# Start the API with real Twilio delivery, reading settings from the git-ignored .env file.
# Messages go ONLY to the numbers in data/manual/test_recipients.csv, and only after an officer
# approves and dispatches an alert in the app.
# Usage (from the project folder):  powershell -ExecutionPolicy Bypass -File scripts\run_twilio.ps1

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { Write-Error ".env not found in $root"; exit 1 }

foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $name, $value = $line -split '=', 2
    $name = $name.Trim(); $value = $value.Trim()
    if ($value) { Set-Item -Path "Env:$name" -Value $value }
}

$recipients = Join-Path $root "data\manual\test_recipients.csv"
if (-not (Test-Path $recipients)) { Write-Error "Create data\manual\test_recipients.csv with your own verified number(s) first"; exit 1 }

# Credentials, plus a sender only for the channels used in the recipients file
$sender = @{ sms = "TWILIO_SMS_FROM"; whatsapp = "TWILIO_WHATSAPP_FROM"; voice = "TWILIO_VOICE_FROM" }
$need = @("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN") + (Import-Csv $recipients | ForEach-Object { $sender[$_.channel] } | Sort-Object -Unique)
$missing = $need | Where-Object { $_ -and -not (Get-Item -Path "Env:$_" -ErrorAction SilentlyContinue) }
if ($missing) { Write-Error "Fill these in .env first: $($missing -join ', ')"; exit 1 }
if ($env:HEAT_PUBLIC_URL) {
    Write-Host "WhatsApp reply bot webhook (paste in Twilio sandbox settings, 'When a message comes in', POST):"
    Write-Host "  $($env:HEAT_PUBLIC_URL.TrimEnd('/'))/whatsapp/inbound" -ForegroundColor Green
    if ($env:HEAT_WHATSAPP_REPLAY) { Write-Host "  replies use approved alerts of replay '$env:HEAT_WHATSAPP_REPLAY'" }
} else {
    Write-Host "HEAT_PUBLIC_URL is empty: the WhatsApp reply bot is off (start 'ngrok http 8000' and put its https address in .env)" -ForegroundColor Yellow
}
$modeText = if ($env:HEAT_DISPATCH_MODE -eq 'twilio') { 'twilio (real outbound sends)' } else { 'simulated (the Dispatch button sends nothing)' }
Write-Host "Dispatch mode: $modeText. Recipients:"
Import-Csv $recipients | Format-Table name, phone, channel, lang -AutoSize

Set-Location $root
& (Join-Path $root ".venv\Scripts\python.exe") -m uvicorn api.main:app --port 8000
