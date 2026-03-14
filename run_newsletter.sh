#!/usr/bin/env bash
# run_newsletter.sh — ForgeCore Newsletter Launcher (Git Bash, models on Git Bash side)

OLLAMA_URL="http://localhost:11434/api/tags"
MAX_WAIT=30
ELAPSED=0

# Path to Ollama binary on the Git Bash/WSL side
# Adjust if ollama is installed elsewhere in your bash PATH
OLLAMA_BIN="${OLLAMA_BIN:-$(which ollama 2>/dev/null)}"

if [ -z "$OLLAMA_BIN" ]; then
    echo "[LAUNCHER] ERROR: ollama not found in PATH. Set OLLAMA_BIN manually."
    exit 1
fi

# Check if Ollama is already serving (don't check tasklist — use the API)
if ! curl -sf "$OLLAMA_URL" > /dev/null 2>&1; then
    echo "[LAUNCHER] Starting Ollama from Git Bash side: $OLLAMA_BIN"
    OLLAMA_MODELS="${OLLAMA_MODELS:-$HOME/.ollama/models}" \
    "$OLLAMA_BIN" serve > /tmp/ollama_serve.log 2>&1 &
    disown
fi

# Wait for Ollama to be ready
echo "[LAUNCHER] Waiting for Ollama on port 11434..."
until curl -sf "$OLLAMA_URL" > /dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
        echo "[LAUNCHER] ERROR: Ollama did not start in ${MAX_WAIT}s. Check /tmp/ollama_serve.log"
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

echo "[LAUNCHER] Ollama ready. Models dir: ${OLLAMA_MODELS:-$HOME/.ollama/models}"
echo "[LAUNCHER] Starting pipeline."
cd "$(dirname "$0")"
python run_pipeline.py
