# NexusAgent Global Installer for Windows
# Registers the premium 'nexus' command globally using the Astral 'uv' toolchain.

$ErrorActionPreference = "Stop"

# Clear host and print a premium ASCII logo
Clear-Host
Write-Host "    _   __                     ___                      __" -ForegroundColor Cyan
Write-Host "   / | / /__  _  __  __ _____ /   | ____ _ ___   ____  / /_" -ForegroundColor Cyan
Write-Host "  /  |/ / _ \| |/_/ / / / ___// /| |/ __ `// _ \ / __ \/ __/" -ForegroundColor Cyan
Write-Host " / /|  /  __/>  <  / /_(__  )/ ___ / /_/ //  __// / / / /__" -ForegroundColor Cyan
Write-Host "/_/ |_/\___/_/|_|  \__,_/____//_/  |_\__, / \___//_/ /_/\__/" -ForegroundColor Cyan
Write-Host "                                    /____/" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "             PREMIUM OFFLINE-FIRST AI CODING AGENT" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "[1/4] Checking System Environment..." -ForegroundColor Yellow

# Verify UV is installed
try {
    $uvVersion = & uv --version
    Write-Host "  * Astral 'uv' detected: $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "  * Astral 'uv' not found. Installing 'uv' via official Astral script..." -ForegroundColor Cyan
    Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1" | Invoke-Expression
    # Add to current path context
    $env:PATH += ";$HOME\.local\bin"
}

# Resolve active project path
$projectDir = Get-Item .
$resolvedPath = $projectDir.FullName
Write-Host "  * Project Path resolved: $resolvedPath" -ForegroundColor Green

Write-Host ""
Write-Host "[2/4] Installing NexusAgent globally via 'uv tool install'..." -ForegroundColor Yellow
try {
    # Install with all extra extensions (gpu, npu, mcp, cloud connectors)
    # Using --editable so any local workspace code changes are reflected globally instantly!
    & uv tool install --force --editable ".[all]"
    Write-Host "  * NexusAgent installed successfully as a global system tool!" -ForegroundColor Green
} catch {
    Write-Host "  * Failed to install using 'uv tool install' with editable mode. Trying standard install..." -ForegroundColor Cyan
    & uv tool install --force ".[all]"
    Write-Host "  * NexusAgent installed successfully as a global system tool!" -ForegroundColor Green
}

Write-Host ""
Write-Host "[3/4] Validating Global Command Execution..." -ForegroundColor Yellow
# Find uv tool bin path
$uvToolPath = Join-Path $env:APPDATA "uv\tools\nexus-agent"
if (Test-Path $uvToolPath) {
    Write-Host "  * Executable registered inside: $uvToolPath" -ForegroundColor Green
}

# Verify command responds
try {
    $nexusVer = & nexus --help | Select-Object -First 1
    Write-Host "  * Global command 'nexus' is active" -ForegroundColor Green
} catch {
    Write-Host "  * Global command registered, but shell PATH needs a reload." -ForegroundColor Cyan
    Write-Host "  * Please restart your terminal or reload environment variables." -ForegroundColor Magenta
}

Write-Host ""
Write-Host "[4/4] Verifying Local Model Library..." -ForegroundColor Yellow
$modelsDir = [System.IO.Path]::Combine($env:USERPROFILE, ".nexus-agent", "models")
if (-not (Test-Path $modelsDir)) {
    New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null
    Write-Host "  * Created empty local model library directory at: $modelsDir" -ForegroundColor Green
} else {
    Write-Host "  * Local model library directory verified at: $modelsDir" -ForegroundColor Green
}

$ggufModels = Get-ChildItem -Path $modelsDir -Filter "*.gguf" -Recurse
if ($ggufModels.Count -gt 0) {
    Write-Host "  * Detected $($ggufModels.Count) local GGUF model(s) ready for offline hosting:" -ForegroundColor Green
    foreach ($m in $ggufModels) {
        $mSizeGB = [Math]::Round($m.Length / 1073741824, 2)
        $mName = $m.Name
        Write-Host "     - $mName ($mSizeGB GB)" -ForegroundColor Cyan
    }
} else {
    Write-Host "  * No local GGUF models detected in $modelsDir yet." -ForegroundColor DarkYellow
    Write-Host "  * Tip: Download a GGUF model and place it in that directory to load models offline." -ForegroundColor Gray
}

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host " You can now run NexusAgent from any folder or drive:"
Write-Host "  * Run 'nexus chat' to launch the premium terminal TUI" -ForegroundColor Green
Write-Host "  * Run 'nexus gui'  to start the responsive web dashboard" -ForegroundColor Green
Write-Host "  * Run 'nexus hardware' to check CPU/GPU/NPU details" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host ""
