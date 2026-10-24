@echo off
REM =============================================================================
REM make_https_cert.bat - HTTPS certificates for the Certificate Manager API
REM
REM Usage:   make_https_cert.bat <server-fixed-ip>
REM Example: make_https_cert.bat 192.168.5.11
REM
REM 1. Creates the college CA once (certs\ca\college_ca.key + certs\college_ca.crt).
REM    Keep certs\ca\college_ca.key private; never copy it to client laptops.
REM 2. Issues the server certificate (certs\server.key + certs\server.crt) for the
REM    given IP, 127.0.0.1, localhost and this computer's name.
REM    Run again whenever the server IP changes; clients keep working because
REM    they trust the CA, not the individual server certificate.
REM 3. Copy certs\college_ca.crt to each client (app folder\certs\college_ca.crt).
REM =============================================================================
setlocal
set "IP=%~1"
if "%IP%"=="" goto usage

set "OPENSSL=C:\AppServ\Apache24\bin\openssl.exe"
if not exist "%OPENSSL%" set "OPENSSL=openssl"
set "CERTS=%~dp0certs"
set "CNF=%CERTS%\openssl_api.cnf"
if not exist "%CERTS%\ca" mkdir "%CERTS%\ca"

REM Names are passed with -subj (the CA and the server must have different names)
> "%CNF%" echo [req]
>>"%CNF%" echo distinguished_name = dn
>>"%CNF%" echo [dn]
>>"%CNF%" echo [ca_ext]
>>"%CNF%" echo basicConstraints = critical, CA:TRUE
>>"%CNF%" echo keyUsage = critical, keyCertSign, cRLSign
>>"%CNF%" echo subjectKeyIdentifier = hash
>>"%CNF%" echo [server_ext]
>>"%CNF%" echo basicConstraints = critical, CA:FALSE
>>"%CNF%" echo keyUsage = critical, digitalSignature, keyEncipherment
>>"%CNF%" echo extendedKeyUsage = serverAuth
>>"%CNF%" echo subjectAltName = IP:%IP%, IP:127.0.0.1, DNS:localhost, DNS:%COMPUTERNAME%
>>"%CNF%" echo subjectKeyIdentifier = hash
>>"%CNF%" echo authorityKeyIdentifier = keyid,issuer

if exist "%CERTS%\ca\college_ca.key" goto issue_server
echo Creating the college CA (valid 10 years)...
"%OPENSSL%" req -x509 -new -nodes -newkey rsa:4096 -sha256 -days 3650 -config "%CNF%" -extensions ca_ext -subj "/CN=College Certificate Authority/O=College of Computer Science and Information Technology" -keyout "%CERTS%\ca\college_ca.key" -out "%CERTS%\college_ca.crt"
if errorlevel 1 goto failed

:issue_server
echo Issuing the server certificate for %IP% (valid 825 days)...
"%OPENSSL%" req -new -nodes -newkey rsa:2048 -sha256 -config "%CNF%" -subj "/CN=Certificate Manager API/O=College of Computer Science and Information Technology" -keyout "%CERTS%\server.key" -out "%CERTS%\server.csr"
if errorlevel 1 goto failed
"%OPENSSL%" x509 -req -sha256 -days 825 -in "%CERTS%\server.csr" -CA "%CERTS%\college_ca.crt" -CAkey "%CERTS%\ca\college_ca.key" -CAcreateserial -extfile "%CNF%" -extensions server_ext -out "%CERTS%\server.crt"
if errorlevel 1 goto failed
del "%CERTS%\server.csr" >nul 2>&1

echo.
echo [SUCCESS] HTTPS certificate ready for %IP%:
echo   Server:  %CERTS%\server.crt + server.key  (used by start_server_https.bat)
echo   Clients: copy %CERTS%\college_ca.crt to each client's certs\ folder
exit /b 0

:usage
echo Usage: %~nx0 ^<server-fixed-ip^>
echo Example: %~nx0 192.168.5.11
exit /b 1

:failed
echo [ERROR] Certificate generation failed.
exit /b 1
