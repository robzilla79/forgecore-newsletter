@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Run deploy.bat first.
    exit /b 1
)

call ".venv\Scripts\activate.bat"

echo [INFO] Building static site...
python publish_site.py
if errorlevel 1 exit /b %errorlevel%

echo [INFO] Deploying to Cloudflare Pages...
python deploy_cloudflare.py
if errorlevel 1 exit /b %errorlevel%

echo [OK] Deploy complete.
exit /b 0