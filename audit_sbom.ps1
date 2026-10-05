# =====================================================================
# NOESIS RC2 SBOM+CVE Audit (W10 Release Checklist step 10/15)
# PowerShell 5+/7+ - Windows primary
# =====================================================================

param(
    [switch]$DryRun,
    [switch]$SkipDockerBuild,
    [switch]$SkipSyft,
    [switch]$SkipTrivy,
    [string]$Dockerfile = "./backend/Dockerfile.laptop",
    [string]$ImageTag = "noesis:0.2.0-rc2-laptop",
    [string]$OutputDir = "./docs/eval/sbom_rc2"
)

$ErrorActionPreference = "Continue"
$script:Warnings = 0
$ExitCode = 0
$script:DryRunCommands = @()

function Write-Banner {
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  NOESIS RC2 SBOM+CVE Audit (W10 Release Checklist step 10/15)" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Log($m)    { Write-Host ("[audit_sbom] " + $m) }
function Write-Ok($m)     { Write-Host ("[audit_sbom][OK ] " + $m) -ForegroundColor Green }
function Write-Warn($m)   { Write-Host ("[audit_sbom][WARN] " + $m) -ForegroundColor Yellow; $script:Warnings++ }
function Write-Err($m)    { Write-Host ("[audit_sbom][ERR ] " + $m) -ForegroundColor Red }
function Write-Dry($m)    { Write-Host ("[audit_sbom][DRY ] " + $m) -ForegroundColor Magenta }

function Test-Cmd($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Add-DryRun($desc, $cmd, $expected) {
    $script:DryRunCommands += @{
        step = $desc
        command = $cmd
        expected_outputs = $expected
    }
}

function Resolve-OutputDir($dir) {
    try {
        $resolved = Resolve-Path $dir -ErrorAction Stop
        return $resolved.Path
    } catch {
        return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $dir))
    }
}

Write-Banner

# -------------------------------------------------------------------
# Resolve output directory
# -------------------------------------------------------------------
$OutputDir = Resolve-OutputDir $OutputDir
Write-Log ("Output directory: {0}" -f $OutputDir)

if (-not (Test-Path $OutputDir)) {
    if ($DryRun) {
        Add-DryRun "Create output directory" ("New-Item -ItemType Directory -Path '{0}' -Force" -f $OutputDir) @($OutputDir)
        Write-Dry ("Would create directory: {0}" -f $OutputDir)
    } else {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
        Write-Ok ("Created directory: {0}" -f $OutputDir)
    }
}

# -------------------------------------------------------------------
# Step 1: Verify Docker CLI
# -------------------------------------------------------------------
Write-Host ""
Write-Log "--- Step 1: Verify Docker CLI ---"

$DockerOk = $false
if (-not $SkipDockerBuild) {
    if (Test-Cmd "docker") {
        if ($DryRun) {
            $verCmd = "docker --version"
            Add-DryRun "Verify Docker CLI" $verCmd @()
            Write-Dry ("Would run: {0}" -f $verCmd)
            $DockerOk = $true
        } else {
            $ver = & docker --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Ok ("Docker found: {0}" -f ($ver -join " "))
                $DockerOk = $true
            } else {
                Write-Warn "docker --version returned non-zero"
            }
        }
    }
    if (-not $DockerOk) {
        Write-Warn "Docker CLI not found - auto-setting SkipDockerBuild to true"
        $SkipDockerBuild = $true
    }
} else {
    Write-Log "SkipDockerBuild set - skipping Docker CLI check"
}

# -------------------------------------------------------------------
# Step 2: Docker build
# -------------------------------------------------------------------
Write-Host ""
Write-Log "--- Step 2: Docker build (3-stage) ---"

if (-not $SkipDockerBuild) {
    $DockerfileFull = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Dockerfile))
    $BuildContext = Split-Path $DockerfileFull -Parent
    $BuildCmd = "docker build -f '{0}' -t {1} '{2}'" -f $DockerfileFull, $ImageTag, $BuildContext

    if ($DryRun) {
        Add-DryRun "Docker 3-stage build" $BuildCmd @("Local image: $ImageTag")
        Write-Dry ("Would run: {0}" -f $BuildCmd)
    } else {
        if (-not (Test-Path $DockerfileFull)) {
            Write-Err ("Dockerfile not found: {0}" -f $DockerfileFull)
            exit 2
        }
        Write-Log ("Running docker build: {0}" -f $BuildCmd)
        Push-Location $BuildContext
        try {
            & docker build -f $DockerfileFull -t $ImageTag .
            if ($LASTEXITCODE -ne 0) {
                Write-Err ("docker build FAILED (exit {0})" -f $LASTEXITCODE)
                exit 2
            }
            Write-Ok ("Docker build succeeded: {0}" -f $ImageTag)
        } finally {
            Pop-Location
        }
    }
} else {
    Write-Log "SkipDockerBuild set - skipping Docker build"
}

# -------------------------------------------------------------------
# Step 3: Syft SBOM
# -------------------------------------------------------------------
Write-Host ""
Write-Log "--- Step 3: Syft SBOM generation ---"

$SbomSpdx    = Join-Path $OutputDir "sbom_laptop.spdx.json"
$SbomCyclone = Join-Path $OutputDir "sbom_laptop.cyclonedx.json"
$SbomTable   = Join-Path $OutputDir "sbom_laptop.table.txt"
$PackageCount = 0

if (-not $SkipSyft) {
    $SyftInstalled = Test-Cmd "syft"
    if (-not $SyftInstalled) {
        if ($DryRun) {
            Write-Dry "syft not installed - would prompt: winget install anchore.syft"
            Write-Dry "Or install from: https://github.com/anchore/syft/releases"
        } else {
            Write-Warn "syft not found on PATH. Install via:"
            Write-Warn "  winget install anchore.syft"
            Write-Warn "  Or download: https://github.com/anchore/syft/releases"
        }
    }

    $SyftOk = $false
    $SyftVerCmd = "syft version"
    $SyftSpdxCmd  = "syft {0} -o spdx-json='{1}'" -f $ImageTag, $SbomSpdx
    $SyftCdxCmd   = "syft {0} -o cyclonedx-json='{1}'" -f $ImageTag, $SbomCyclone
    $SyftTableCmd = "syft {0} -o table='{1}'" -f $ImageTag, $SbomTable

    if ($DryRun) {
        Add-DryRun "Verify syft installed" $SyftVerCmd @()
        Add-DryRun "Generate SPDX JSON SBOM" $SyftSpdxCmd @($SbomSpdx)
        Add-DryRun "Generate CycloneDX JSON SBOM" $SyftCdxCmd @($SbomCyclone)
        Add-DryRun "Generate table SBOM + count packages" $SyftTableCmd @($SbomTable)
        Write-Dry ("Would run: {0}" -f $SyftVerCmd)
        Write-Dry ("Would run: {0}" -f $SyftSpdxCmd)
        Write-Dry ("Would run: {0}" -f $SyftCdxCmd)
        Write-Dry ("Would run: {0}" -f $SyftTableCmd)
    } else {
        if (-not $SyftInstalled) {
            Write-Err "syft not installed - cannot generate SBOM"
        } else {
            Write-Ok ("syft found: {0}" -f (& syft version 2>&1 | Select-Object -First 1))

            Write-Log ("Generating SPDX SBOM -> {0}" -f $SbomSpdx)
            & syft $ImageTag -o ("spdx-json=" + $SbomSpdx) --quiet
            if ($LASTEXITCODE -ne 0) { Write-Warn "syft SPDX generation failed" }

            Write-Log ("Generating CycloneDX SBOM -> {0}" -f $SbomCyclone)
            & syft $ImageTag -o ("cyclonedx-json=" + $SbomCyclone) --quiet
            if ($LASTEXITCODE -ne 0) { Write-Warn "syft CycloneDX generation failed" }

            Write-Log ("Generating table SBOM -> {0}" -f $SbomTable)
            & syft $ImageTag -o ("table=" + $SbomTable) --quiet
            if ($LASTEXITCODE -ne 0) { Write-Warn "syft table generation failed" }

            if (Test-Path $SbomTable) {
                $lines = (Get-Content $SbomTable | Measure-Object -Line).Lines
                if ($lines -gt 2) { $PackageCount = [Math]::Max(0, $lines - 3) }
                Write-Ok ("Syft SBOMs generated - {0} packages detected" -f $PackageCount)
                $SyftOk = $true
            }
        }
    }
} else {
    Write-Log "SkipSyft set - skipping SBOM generation"
}

# -------------------------------------------------------------------
# Step 4: Trivy CVE scan
# -------------------------------------------------------------------
Write-Host ""
Write-Log "--- Step 4: Trivy CVE scan ---"

$TrivySarif = Join-Path $OutputDir "trivy_laptop_image.sarif.json"
$TrivyFull  = Join-Path $OutputDir "trivy_laptop_image.full.txt"
$CveSummary = Join-Path $OutputDir "cve_summary.json"
$CveCounts = @{ critical = 0; high = 0; medium = 0; low = 0; unknown = 0 }

if (-not $SkipTrivy) {
    $TrivyInstalled = Test-Cmd "trivy"
    if (-not $TrivyInstalled) {
        if ($DryRun) {
            Write-Dry "trivy not installed - would prompt install from: https://github.com/aquasecurity/trivy/releases"
        } else {
            Write-Warn "trivy not found on PATH. Install from: https://github.com/aquasecurity/trivy/releases"
        }
    }

    $TrivyVerCmd    = "trivy --version"
    $TrivySarifCmd  = "trivy image --format sarif --output '{0}' {1}" -f $TrivySarif, $ImageTag
    $TrivyFullCmd   = "trivy image --format table --output '{0}' {1}" -f $TrivyFull, $ImageTag

    if ($DryRun) {
        Add-DryRun "Verify trivy installed" $TrivyVerCmd @()
        Add-DryRun "Trivy SARIF CVE report" $TrivySarifCmd @($TrivySarif)
        Add-DryRun "Trivy table full report" $TrivyFullCmd @($TrivyFull)
        Add-DryRun "Parse CVE counts -> cve_summary.json" ("parse {0} + write {1}" -f $TrivyFull, $CveSummary) @($CveSummary)
        Write-Dry ("Would run: {0}" -f $TrivyVerCmd)
        Write-Dry ("Would run: {0}" -f $TrivySarifCmd)
        Write-Dry ("Would run: {0}" -f $TrivyFullCmd)
    } else {
        if (-not $TrivyInstalled) {
            Write-Err "trivy not installed - cannot run CVE scan"
        } else {
            Write-Ok ("trivy found: {0}" -f (& trivy --version 2>&1 | Select-Object -First 1))

            Write-Log ("Running Trivy SARIF scan -> {0}" -f $TrivySarif)
            & trivy image --format sarif --output $TrivySarif $ImageTag 2>&1 | Out-Null

            Write-Log ("Running Trivy full table scan -> {0}" -f $TrivyFull)
            & trivy image --format table --output $TrivyFull $ImageTag 2>&1 | Out-Null

            if (Test-Path $TrivyFull) {
                $raw = Get-Content $TrivyFull -Raw
                $matchesCrit = [regex]::Matches($raw, '(?im)^\s*CRITICAL\s*\|\s*(\d+)\s*$')
                $sum = 0; foreach ($m in $matchesCrit) { $sum += [int]$m.Groups[1].Value }
                $CveCounts.critical = $sum

                $matchesHigh = [regex]::Matches($raw, '(?im)^\s*HIGH\s*\|\s*(\d+)\s*$')
                $sum = 0; foreach ($m in $matchesHigh) { $sum += [int]$m.Groups[1].Value }
                $CveCounts.high = $sum

                $matchesMed = [regex]::Matches($raw, '(?im)^\s*MEDIUM\s*\|\s*(\d+)\s*$')
                $sum = 0; foreach ($m in $matchesMed) { $sum += [int]$m.Groups[1].Value }
                $CveCounts.medium = $sum

                $matchesLow = [regex]::Matches($raw, '(?im)^\s*LOW\s*\|\s*(\d+)\s*$')
                $sum = 0; foreach ($m in $matchesLow) { $sum += [int]$m.Groups[1].Value }
                $CveCounts.low = $sum

                $matchesUnk = [regex]::Matches($raw, '(?im)^\s*UNKNOWN\s*\|\s*(\d+)\s*$')
                $sum = 0; foreach ($m in $matchesUnk) { $sum += [int]$m.Groups[1].Value }
                $CveCounts.unknown = $sum

                $CveCounts | ConvertTo-Json -Depth 3 | Set-Content $CveSummary -Encoding UTF8
                Write-Ok ("CVE summary written: CRITICAL={0}, HIGH={1}, MEDIUM={2}, LOW={3}, UNKNOWN={4}" -f
                    $CveCounts.critical, $CveCounts.high, $CveCounts.medium, $CveCounts.low, $CveCounts.unknown)
            }
        }
    }
} else {
    Write-Log "SkipTrivy set - skipping CVE scan"
}

# -------------------------------------------------------------------
# Step 5: Changelog scan
# -------------------------------------------------------------------
Write-Host ""
Write-Log "--- Step 5: Changelog + release checklist scan ---"

$ChangelogPath = Join-Path (Get-Location) "CHANGELOG.md"
$ChecklistPath = Join-Path (Get-Location) "RELEASE_CHECKLIST_v0.2.0_rc2.md"
$ChangelogOk = $false

$ChkScanCmd = "Check CHANGELOG.md for v0.2.0-rc2 section + match RELEASE_CHECKLIST items"

if ($DryRun) {
    Add-DryRun "Changelog verification" $ChkScanCmd @()
    Write-Dry ("Would read {0} and {1}" -f $ChangelogPath, $ChecklistPath)
} else {
    if (Test-Path $ChangelogPath) {
        $cl = Get-Content $ChangelogPath -Raw
        $hasRc2 = $cl -match "0\.2\.0.*rc2|v0\.2\.0-rc2|Unreleased"
        if ($hasRc2) {
            Write-Ok "CHANGELOG.md contains release markers (Unreleased/v0.2.0-rc2 patterns)"
            $ChangelogOk = $true
        } else {
            Write-Warn "CHANGELOG.md found but no v0.2.0-rc2 section marker"
        }
    } else {
        Write-Warn "CHANGELOG.md not found in project root"
    }

    if (Test-Path $ChecklistPath) {
        $rc = Get-Content $ChecklistPath -Raw
        $step10 = $rc -match "step 10|Trivy.*HIGH.*CRITICAL|SBOM.*syft"
        if ($step10) {
            Write-Ok "RELEASE_CHECKLIST step 10 items (SBOM+CVE) referenced"
        } else {
            Write-Warn "RELEASE_CHECKLIST found but step 10 markers missing"
        }
    } else {
        Write-Warn "RELEASE_CHECKLIST_v0.2.0_rc2.md not found in project root"
    }
}

# -------------------------------------------------------------------
# Step 6: SBOM output verification + summary table
# -------------------------------------------------------------------
Write-Host ""
Write-Log "--- Step 6: Output verification + summary ---"

$VerifyOk = $true
$ExpectedFiles = @(
    @{ name = "SBOM SPDX JSON";       path = $SbomSpdx;    skip = $SkipSyft },
    @{ name = "SBOM CycloneDX JSON";  path = $SbomCyclone; skip = $SkipSyft },
    @{ name = "SBOM table text";      path = $SbomTable;   skip = $SkipSyft },
    @{ name = "Trivy SARIF report";   path = $TrivySarif;  skip = $SkipTrivy },
    @{ name = "Trivy full report";    path = $TrivyFull;   skip = $SkipTrivy },
    @{ name = "CVE summary JSON";     path = $CveSummary;  skip = $SkipTrivy }
)

Write-Host ("{0,-25} {1,-8} {2,-12} {3}" -f "FILE", "EXISTS", "SIZE_BYTES", "PATH") -ForegroundColor Cyan
foreach ($f in $ExpectedFiles) {
    $exists = $false
    $size = 0
    if (-not $f.skip) {
        if ($DryRun) {
            Write-Dry ("Would check existence/size of: {0}" -f $f.path)
            $exists = $true; $size = 0
        } else {
            $exists = (Test-Path $f.path) -and ((Get-Item $f.path).Length -gt 0)
            if ($exists) { $size = (Get-Item $f.path).Length }
            if (-not $exists) {
                Write-Warn ("Missing or empty: {0}" -f $f.name)
                $VerifyOk = $false
            }
        }
    }
    if ($f.skip) { $status = "SKIP"; $color = "Gray" }
    elseif ($exists) { $status = "OK"; $color = "Green" }
    else { $status = "MISS"; $color = "Red" }
    Write-Host ("{0,-25} {1,-8} {2,-12} {3}" -f $f.name, $status, $size, $f.path) -ForegroundColor $color
}

# -------------------------------------------------------------------
# DryRun: write dryrun_plan.json and exit
# -------------------------------------------------------------------
if ($DryRun) {
    $DryRunPlan = @{
        generated_at = (Get-Date -Format "o")
        params = @{
            DryRun         = $DryRun.IsPresent
            SkipDockerBuild = $SkipDockerBuild.IsPresent
            SkipSyft        = $SkipSyft.IsPresent
            SkipTrivy       = $SkipTrivy.IsPresent
            Dockerfile      = $Dockerfile
            ImageTag        = $ImageTag
            OutputDir       = $OutputDir
        }
        steps = $script:DryRunCommands
    }
    $DryPlanPath = Join-Path $OutputDir "dryrun_plan.json"
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }
    $DryRunPlan | ConvertTo-Json -Depth 6 | Set-Content $DryPlanPath -Encoding UTF8
    Write-Host ""
    Write-Ok ("DryRun plan written: {0}" -f $DryPlanPath)
    Write-Ok ("DryRun commands count: {0}" -f $script:DryRunCommands.Count)
    exit 0
}

# -------------------------------------------------------------------
# Step 7: Exit code determination
# -------------------------------------------------------------------
Write-Host ""
Write-Log "--- Step 7: Exit code determination ---"

if ($CveCounts.critical -ge 1) {
    Write-Err ("CVE CRITICAL count = {0} -> exit 4" -f $CveCounts.critical)
    exit 4
}

if (-not $VerifyOk) {
    Write-Err "SBOM/CVE outputs missing or empty -> exit 3"
    exit 3
}

if ($script:Warnings -gt 0) {
    Write-Warn ("{0} warning(s) encountered -> exit 1" -f $script:Warnings)
    exit 1
}

Write-Ok "All checks passed cleanly -> exit 0"
exit 0
