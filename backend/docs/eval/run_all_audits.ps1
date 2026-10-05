# Noesis Combined Audit Runner (PowerShell)
# ------------------------------------------
# Runs 4 audit pipelines and collects outputs to docs/eval/ with a
# timestamped index.txt manifest.  Invoke from the backend/ directory:
#   cd backend ; .\docs\eval\run_all_audits.ps1
#
# Audits:
#   (a) audit_mac_spawn.py              -- 4 Viva deny scenarios
#   (b) determinism_manifest.py         -- C3 bit-exact reproducibility
#   (c) audit_llm_providers.py          -- 4 LLM provider smoke audit
#   (d) test_memory_promotion           -- FUTURE PLACEHOLDER (unit test)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# -------------------------------------------------------------------
# Paths (relative to repo root => must be in backend/ when invoking)
# -------------------------------------------------------------------
$RepoBackend = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path | Split-Path
$ScriptsDir  = Join-Path $RepoBackend "scripts"
$TestsDir    = Join-Path $RepoBackend "tests"
$EvalDir     = Join-Path $RepoBackend "docs" "eval"
$Timestamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$IndexFile   = Join-Path $EvalDir ("index_" + $Timestamp + ".txt")

if (-not (Test-Path $EvalDir)) {
    New-Item -ItemType Directory -Path $EvalDir -Force | Out-Null
}

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
function Write-IndexLine {
    param([string]$Text)
    Add-Content -Path $IndexFile -Value $Text
    Write-Host $Text
}

function Invoke-AuditStep {
    param(
        [string]$Label,
        [string]$Command,
        [string]$Arguments,
        [string]$OutputFile = $null
    )
    $stepStart = Get-Date
    Write-IndexLine ""
    Write-IndexLine ("============================================================")
    Write-IndexLine ("STEP: " + $Label)
    Write-IndexLine ("TIME: " + $stepStart.ToString("o"))
    Write-IndexLine ("CMD : py " + $Command + " " + $Arguments)
    Write-IndexLine ("------------------------------------------------------------")

    if ($OutputFile) {
        $logOut = Join-Path $EvalDir ($OutputFile + ".stdout.log")
        $logErr = Join-Path $EvalDir ($OutputFile + ".stderr.log")
        $proc = Start-Process -FilePath "py" -ArgumentList @($Command) + ($Arguments -split ' ') `
            -WorkingDirectory $RepoBackend `
            -RedirectStandardOutput $logOut `
            -RedirectStandardError  $logErr `
            -PassThru -Wait -NoNewWindow
        $exitCode = $proc.ExitCode
        if (Test-Path $logOut) { Write-IndexLine ("STDOUT -> " + $logOut) }
        if (Test-Path $logErr) { Write-IndexLine ("STDERR -> " + $logErr) }
    } else {
        $proc = Start-Process -FilePath "py" -ArgumentList @($Command) + ($Arguments -split ' ') `
            -WorkingDirectory $RepoBackend `
            -PassThru -Wait -NoNewWindow
        $exitCode = $proc.ExitCode
    }

    $stepEnd = Get-Date
    $dur = ($stepEnd - $stepStart).TotalSeconds
    Write-IndexLine ("EXIT: " + $exitCode + "  |  duration " + $dur.ToString("F1") + "s")
    Write-IndexLine ("------------------------------------------------------------")
    return $exitCode
}

# -------------------------------------------------------------------
# Manifest header
# -------------------------------------------------------------------
Write-IndexLine ("NOESIS AUDIT RUN INDEX")
Write-IndexLine ("Generated : " + (Get-Date -Format "o"))
Write-IndexLine ("Backend   : " + $RepoBackend)
Write-IndexLine ("Python    : " + (& { py --version 2>&1 }))

# -------------------------------------------------------------------
# (a) audit_mac_spawn.py
# -------------------------------------------------------------------
$exitA = Invoke-AuditStep `
    -Label "(a) MAC Spawn Audit (4 Viva Deny Scenarios)" `
    -Command (Join-Path $ScriptsDir "audit_mac_spawn.py") `
    -Arguments "" `
    -OutputFile ("audit_mac_spawn_" + $Timestamp)

# -------------------------------------------------------------------
# (b) determinism_manifest.py --runs 5 --seeds 42
# -------------------------------------------------------------------
$detOutBase = "determinism_manifest_" + $Timestamp
$detCsv     = Join-Path $EvalDir ($detOutBase + ".csv")
$exitB = Invoke-AuditStep `
    -Label "(b) Determinism Manifest (C3) --runs 5 --seeds 42" `
    -Command (Join-Path $ScriptsDir "determinism_manifest.py") `
    -Arguments ("--runs 5 --seeds 42 --output " + $detCsv) `
    -OutputFile $detOutBase
if (Test-Path $detCsv) {
    Write-IndexLine ("CSV   -> " + $detCsv)
}
$detJson = [System.IO.Path]::ChangeExtension($detCsv, ".summary.json")
if (Test-Path $detJson) {
    Write-IndexLine ("JSON  -> " + $detJson)
}

# -------------------------------------------------------------------
# (c) audit_llm_providers.py
# -------------------------------------------------------------------
$exitC = Invoke-AuditStep `
    -Label "(c) LLM Provider Audit (4 providers, deterministic mock)" `
    -Command (Join-Path $ScriptsDir "audit_llm_providers.py") `
    -Arguments "" `
    -OutputFile ("audit_llm_providers_" + $Timestamp)

# -------------------------------------------------------------------
# (d) FUTURE PLACEHOLDER: test_memory_promotion
# -------------------------------------------------------------------
$memTest = Join-Path $TestsDir "unit" "test_memory_promotion.py"
Write-IndexLine ""
Write-IndexLine ("============================================================")
Write-IndexLine ("STEP: (d) Memory Promotion (FUTURE PLACEHOLDER)")
Write-IndexLine ("TIME: " + (Get-Date -Format "o"))
Write-IndexLine ("------------------------------------------------------------")
if (Test-Path $memTest) {
    Write-IndexLine ("Test module exists: " + $memTest)
    Write-IndexLine ("Placeholder: not invoking pytest in this audit bundle.")
    Write-IndexLine ("(Future) CMD: py -m pytest " + $memTest + " -v")
    $exitD = 0
} else {
    Write-IndexLine ("Test module NOT found at expected path: " + $memTest)
    Write-IndexLine ("Placeholder marker kept for future wiring.")
    $exitD = 0
}
Write-IndexLine ("EXIT: " + $exitD + "  (placeholder — always 0)")
Write-IndexLine ("------------------------------------------------------------")

# -------------------------------------------------------------------
# Final summary
# -------------------------------------------------------------------
$Overall = if (($exitA -eq 0) -and ($exitB -eq 0) -and ($exitC -eq 0) -and ($exitD -eq 0)) { "PASS" } else { "FAIL" }
Write-IndexLine ""
Write-IndexLine ("============================================================")
Write-IndexLine ("AUDIT BUNDLE SUMMARY")
Write-IndexLine ("  (a) audit_mac_spawn.py          exit=" + $exitA)
Write-IndexLine ("  (b) determinism_manifest.py     exit=" + $exitB + "  [--runs 5 --seeds 42]")
Write-IndexLine ("  (c) audit_llm_providers.py      exit=" + $exitC)
Write-IndexLine ("  (d) test_memory_promotion       exit=" + $exitD + "  (placeholder)")
Write-IndexLine ("OVERALL: " + $Overall)
Write-IndexLine ("INDEX  : " + $IndexFile)
Write-IndexLine ("============================================================")

Write-Host ""
Write-Host ("Audit index written to: " + $IndexFile) -ForegroundColor Cyan
if ($Overall -eq "FAIL") {
    exit 1
}
exit 0
