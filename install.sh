#!/bin/bash
# NexusAgent Global Installer for Linux/macOS
# Registers the 'nexus' command globally using the Astral 'uv' toolchain.

set -e

# ASCII logo
echo ""
echo "    _   __                     ___                      __"
echo "   / | / /__  _  __  __ _____ /   | ____ _ ___   ____  / /_"
echo "  /  |/ / _ \| |/_/ / / / ___// /| |/ __ \`// _ \ / __ \/ __/"
echo " / /|  /  __/>  <  / /_(__  )/ ___ / /_/ //  __// / / / /__"
echo "/_/ |_/\___/_/|_|  \__,_/____//_/  |_\__, / \___//_/ /_/\__/"
echo "                                    /____/"
echo "============================================================="
echo "             PREMIUM OFFLINE-FIRST AI CODING AGENT"
echo "============================================================="
echo ""

# Detect OS
OS="$(uname -s)"
echo "[1/4] Checking System Environment..."
echo "  * Detected OS: $OS"

# Check for uv
if command -v uv &> /dev/null; then
    echo "  * Astral 'uv' detected: $(uv --version)"
else
    echo "  * Astral 'uv' not found. Installing 'uv'..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
fi

echo ""
echo "[2/4] Installing NexusAgent globally via 'uv tool install'..."
if uv tool install --force ".[all]" 2>&1; then
    echo "  * NexusAgent installed successfully as a global system tool!"
else
    echo "  * Failed with editable mode. Trying standard install..."
    uv tool install --force ".[all]"
fi

echo ""
echo "[3/4] Validating Global Command Execution..."
if nexus --help &> /dev/null; then
    echo "  * Global command 'nexus' is active"
else
    echo "  * Command registered, but shell PATH needs reload."
    echo "  * Please restart your terminal or run: source ~/.bashrc"
fi

echo ""
echo "[4/4] Verifying Local Model Library..."
MODELS_DIR="$HOME/.nexus-agent/models"
if [ ! -d "$MODELS_DIR" ]; then
    mkdir -p "$MODELS_DIR"
    echo "  * Created local model library directory at: $MODELS_DIR"
else
    echo "  * Local model library directory verified at: $MODELS_DIR"
fi

GGUF_COUNT=$(find "$MODELS_DIR" -name "*.gguf" 2>/dev/null | wc -l)
if [ "$GGUF_COUNT" -gt 0 ]; then
    echo "  * Detected $GGUF_COUNT local GGUF model(s) ready for offline hosting:"
    find "$MODELS_DIR" -name "*.gguf" -exec basename {} \; | while read m; do
        echo "     - $m"
    done
else
    echo "  * No local GGUF models detected yet."
    echo "  * Tip: Download a GGUF model and place it in $MODELS_DIR"
fi

echo ""
echo "============================================================="
echo "  INSTALLATION COMPLETE!"
echo "============================================================="
echo " You can now run NexusAgent from any folder:"
echo "  * Run 'nexus chat' to launch the premium terminal TUI"
echo "  * Run 'nexus gui'  to start the responsive web dashboard"
echo "  * Run 'nexus hardware' to check CPU/GPU/NPU details"
echo "============================================================="
echo ""