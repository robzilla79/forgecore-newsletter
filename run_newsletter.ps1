# run_newsletter.ps1 — ForgeCore Newsletter Launcher
# Ensures Ollama is running before starting the pipeline

$OllamaUrl = "http://localhost:11434/api/tags"
$MaxWait = 30  # seconds
$Elapsed = 0

# Start Ollama if not already running
if (-not (Get-Process "ollama" -ErrorAction SilentlyContinue)) {
    Write-Host "[LAUNCHER] Starting Ollama..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
}

# Wait for Ollama to be ready
Write-Host "[LAUNCHER] Waiting for Ollama on port 11434..."
while ($Elapsed -lt $MaxWait) {
    try {
        $r = Invoke-WebRequest -Uri $OllamaUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            Write-Host "[LAUNCHER] Ollama ready. Starting pipeline."
            break
        }
    } catch {}
    Start-Sleep -Seconds 2
    $Elapsed += 2
}

if ($Elapsed -ge $MaxWait) {
    Write-Host "[LAUNCHER] ERROR: Ollama did not start in ${MaxWait}s. Aborting." -ForegroundColor Red
    exit 1
}

# Run the newsletter pipeline
cd $PSScriptRoot
python run_pipeline.py
