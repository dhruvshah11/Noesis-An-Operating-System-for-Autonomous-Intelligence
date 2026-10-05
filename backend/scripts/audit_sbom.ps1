# =====================================================================
# Noesis SBOM Audit Script (PowerShell — Windows native)
# MS9 deliverable — invoke from backend/ directory:
#
#   cd backend ; .\scripts\audit_sbom.ps1
#
# Steps:
#   1. Install syft + trivy (scoop/choco install lines commented out
#      below — uncomment one block once, or install manually).
#   2. Generate SPDX-JSON SBOM of the laptop Dockerfile into dist/.
#   3. Run Trivy image scan against local/noesis:0.2.0-rc2 with
#      --severity HIGH,CRITICAL --exit-code 1.
#
# Exit codes:
#   0  SBOM generated + 0 HIGH/CRITICAL findings.
#   1  Trivy found at least one HIGH or CRITICAL vulnerability.
#   2  Missing prerequisite (docker, syft, or trivy not on PATH).
# =====================================================================

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path
$DistDir    = Join-Path $BackendDir "dist"
$ImageTag   = "local/noesis:0.2.0-rc2"
$SbomOut    = Join-Path $DistDir "noesis-sbom.spdx.json"
$TrivyIgnore = Join-Path $BackendDir "sbom" "trivyignore"

function Write-Log($m)  { Write-Host ("[audit_sbom] " + $m) }
function Write-Warn($m) { Write-Host ("[audit_sbom][WARN] " + $m) -ForegroundColor Yellow }
function Write-Err($m)  { Write-Host ("[audit_sbom][ERR ] " + $m) -ForegroundColor Red }

if (-not (Test-Path $DistDir)) {
    New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
}

# -------------------------------------------------------------------
# Prerequisite checks
# -------------------------------------------------------------------
function Test-Cmd($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

foreach ($cmd in @("docker", "syft", "trivy")) {
    if (-not (Test-Cmd $cmd)) {
        Write-Err ("missing prerequisite: '{0}' not found on PATH." -f $cmd)
        Write-Warn "Install hints (uncomment one block below, or run manually):"
        Write-Warn "  Scoop (Windows):    scoop install syft trivy"
        Write-Warn "  Chocolatey:         choco install syft trivy -y"
        Write-Warn "  WinGet:             winget install Anchore.Syft AquaSecurity.Trivy"
        exit 2
    }
}

# -------------------------------------------------------------------
# Optional: one-line installers (kept commented — user opts in)
# -------------------------------------------------------------------
# scoop install syft trivy
# choco install syft trivy -y
# winget install --id=Anchore.Syft -e  ; winget install --id=AquaSecurity.Trivy -e

# -------------------------------------------------------------------
# Step 1 — ensure the image is built locally
# -------------------------------------------------------------------
$imgPresent = (& docker image inspect $ImageTag 2>$null; $LASTEXITCODE -eq 0)
if (-not $imgPresent) {
    Write-Log ("Image {0} not found locally — running docker build now." -f $ImageTag)
    Push-Location $BackendDir
    try {
        & docker build -f Dockerfile.laptop -t $ImageTag .
        if ($LASTEXITCODE -ne 0) { throw "docker build failed (exit $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
}

# -------------------------------------------------------------------
# Step 2 — syft SBOM (SPDX-JSON) into dist/
# -------------------------------------------------------------------
Write-Log ("Generating SPDX-JSON SBOM via syft -> {0}" -f $SbomOut)
& syft packages (Join-Path $BackendDir "Dockerfile.laptop") `
    -o ("spdx-json=" + $SbomOut) `
    --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Err "syft exited non-zero — SBOM probably not written."
    exit 2
}
if (-not (Test-Path $SbomOut) -or ((Get-Item $SbomOut).Length -eq 0)) {
    Write-Err ("SBOM output is empty or missing at {0}" -f $SbomOut)
    exit 2
}
$size = (Get-Item $SbomOut).Length
Write-Log ("SBOM written: {0} ({1} bytes)" -f $SbomOut, $size)

# -------------------------------------------------------------------
# Step 3 — Trivy HIGH/CRITICAL scan with exit-code 1 gating
# -------------------------------------------------------------------
Write-Log "Running Trivy image scan (HIGH + CRITICAL only, gated)..."
& trivy image `
    --severity HIGH,CRITICAL `
    --exit-code 1 `
    --no-progress `
    --ignorefile $TrivyIgnore `
    $ImageTag

$trivyExit = $LASTEXITCODE
if ($trivyExit -eq 0) {
    Write-Log "Trivy scan: PASS (0 HIGH / 0 CRITICAL findings)."
} else {
    Write-Err ("Trivy scan: FAIL (exit {0}). Fix vulnerabilities above, then re-run." -f $trivyExit)
    exit $trivyExit
}

Write-Log "SBOM audit complete."
exit 0
