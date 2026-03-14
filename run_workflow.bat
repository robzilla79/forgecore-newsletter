@echo off
setlocal enabledelayedexpansion

rem Jump to this script's directory
cd /d %~dp0

echo [preflight] Killing any running Ollama processes...
powershell -Command "Get-Process | Where-Object { $_.ProcessName -like '*ollama*' } | Stop-Process -Force -ErrorAction SilentlyContinue"

echo [preflight] Starting Ollama server...
start "ollama-serve" /min ollama serve

rem Small delay to let Ollama bind to 11434
timeout /t 3 /nobreak >nul

echo [preflight] Ensuring virtualenv exists...
if not exist .venv (
  py -m venv .venv
)

echo [preflight] Activating virtualenv...
call .venv\Scripts\activate.bat

echo [preflight] Upgrading pip and installing core requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [preflight] Installing lxml html_clean extras for trafilatura...
python -m pip install "lxml[html_clean]" lxml_html_clean

echo [preflight] Installing Cloudflare Wrangler globally if needed...
where wrangler >nul 2>&1
if errorlevel 1 (
  echo [preflight] Wrangler not found; installing with npm...
  npm install -g wrangler@4.73.0
) else (
  echo [preflight] Wrangler already installed.
)

echo [run] Launching agent_loop.py all...
python agent_loop.py all

echo [done] Workflow finished. Check HEARTBEAT.md and state\errors.log if anything failed.

endlocal
