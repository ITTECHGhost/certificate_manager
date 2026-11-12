@echo off
REM =============================================================================
REM 2_CHECK_SERVER_CONNECTION.bat - is the server reachable from this laptop?
REM Run it on any client laptop. Checks: network (ping), port (firewall), API (/ping).
REM =============================================================================
setlocal
set "IP=172.50.1.100"
set "PORT=2030"
set /p "IP=Server IP [%IP%]: "
set /p "PORT=Port [%PORT%]: "
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ip='%IP%'; $port=%PORT%;" ^
  "Write-Host ''; Write-Host '1. Network (ping)...';" ^
  "if (Test-Connection $ip -Count 2 -Quiet) { Write-Host '   OK - the server laptop answers' -F Green } else { Write-Host '   NO ANSWER - server off, wrong IP, or ping blocked (try step 2 anyway)' -F Yellow };" ^
  "Write-Host '2. Port' $port '(firewall / service)...';" ^
  "$tcp = Test-NetConnection $ip -Port $port -WarningAction SilentlyContinue;" ^
  "if ($tcp.TcpTestSucceeded) { Write-Host '   OK - the port is open' -F Green } else { Write-Host '   CLOSED - on the server: is the FastAPICertificateManager service running? is the firewall rule there?' -F Red; exit 1 };" ^
  "Write-Host '3. API answer (/ping)...';" ^
  "$ok=$false; foreach ($s in 'https','http') { $b = & curl.exe -s -k -m 8 ($s + '://' + $ip + ':' + $port + '/ping'); if ($LASTEXITCODE -eq 0 -and $b -match 'online') { Write-Host ('   OK - ' + $s + ' answers: ' + $b) -F Green; $ok=$true; break } };" ^
  "if (-not $ok) { Write-Host '   NO ANSWER - port open but the API does not reply: see logs\api_service.log on the server' -F Red; exit 1 };" ^
  "Write-Host ''; Write-Host 'ALL GOOD - this laptop can use the server.' -F Green"
echo.
pause
