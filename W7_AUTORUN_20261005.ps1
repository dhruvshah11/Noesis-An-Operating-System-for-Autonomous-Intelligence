# =====================================================================
# NOESIS - W7 WEEKEND FULL BENCHMARK AUTORUN - v0.2.0-rc2
# =====================================================================
# SINGLE DOUBLE-CLICK DOES EVERYTHING:
#   0. Self-elevate to ADMIN (required for winget installs)
#   1. Detect + prompt for winget (Microsoft.DesktopAppInstaller) if missing
#   2. winget install Ollama.Ollama (UAC prompt once)
#   3. Start ollama serve background process
#   4. Pull qwen2.5-coder:7b-instruct-q4_K_M (4.7 GB)
#   5. Pull deepseek-coder-v2:16b-lite-instruct-q4_K_M (9.4 GB - optional)
#   6. powercfg /setactive HIGH PERFORMANCE GUID
#   7. Ping guard: py backend\scripts\ollama_ping.py (exit 0 required)
#   8. FULL BENCHMARK: py backend\scripts\run_w7_weekend.py --full
#       SE50-50x3 -> HumanEval-164 -> MBPP-500 -> MS8 stats -> Ablation
#   9. Post-process: publish tables_for_paper_LATEST.json + merge thesis Ch06
#  10. DONE: console BEEP x3 + summary screen + master log
# =====================================================================
# USAGE (Dhruv Shah UPES laptop):
#   a) Explorer -> right-click this .ps1 -> "Run with PowerShell"
#   b) Or from elevated PowerShell:
#      powershell -ExecutionPolicy Bypass -File W7_AUTORUN_20261005.ps1
#      powershell -ExecutionPolicy Bypass -File W7_AUTORUN_20261005.ps1 -SkipDeepSeek
#      powershell -ExecutionPolicy Bypass -File W7_AUTORUN_20261005.ps1 -DryRunOnly
# =====================================================================

[CmdletBinding()]
param(
    [switch]$SkipDeepSeek = $false,
    [switch]$DryRunOnly = $false,
    [string]$OutDirSuffix = "Oct05_real"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# =====================================================================
# GLOBAL ERROR TRAP — catches ALL crashes, PAUSES (window never closes)
#   Replaces old try/catch which caused parser errors.
# =====================================================================
$Global:W7_MASTER_LOG_PATH = ''
trap {
    Write-Host ''
    Write-Host '========================================================================' -ForegroundColor Red
    Write-Host '=== 🔴 SCRIPT CRASHED (GLOBAL TRAP FIRED) ===' -ForegroundColor Red
    Write-Host '========================================================================' -ForegroundColor Red
    Write-Host ''
    Write-Host ('Exception type: ' + $_.Exception.GetType().FullName) -ForegroundColor Red
    Write-Host ('Message       : ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ''
    Write-Host 'Stack trace (ScriptStackTrace):' -ForegroundColor Yellow
    Write-Host $_.ScriptStackTrace -ForegroundColor Yellow
    Write-Host ''
    try {
        Write-Host ('Line #' + $_.InvocationInfo.ScriptLineNumber + ' (col ' + $_.InvocationInfo.OffsetInLine + '):') -ForegroundColor Yellow
        Write-Host ('  >>> ' + $_.InvocationInfo.Line) -ForegroundColor Yellow
        $errLine = Get-Content $MyInvocation.MyCommand.Path -TotalCount ($_.InvocationInfo.ScriptLineNumber) | Select-Object -Last 1
        Write-Host ('  Actual line text: ' + $errLine) -ForegroundColor Yellow
    } catch {}
    if ($Global:W7_MASTER_LOG_PATH -and (Test-Path $Global:W7_MASTER_LOG_PATH)) {
        Write-Host ''
        Write-Host ('Master log path: ' + $Global:W7_MASTER_LOG_PATH) -ForegroundColor Cyan
    }
    Write-Host ''
    Write-Host '📋 PASTE THE ENTIRE RED SCREEN OUTPUT ABOVE TO YOUR ASSISTANT FOR DEBUG.'
    Write-Host ''
    Read-Host 'Press ENTER to close this window.'
    exit 99
}

# ---------------------------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------------------------
$REPO_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = Join-Path $REPO_ROOT "backend"
$LOG_DIR = Join-Path $REPO_ROOT "docs\eval\w7_autorun_logs"
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$MASTER_LOG = Join-Path $LOG_DIR "W7_AUTORUN_$TIMESTAMP.log"
$PRIMARY_MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"
$SECONDARY_MODEL = "deepseek-coder-v2:16b-lite-instruct-q4_K_M"
$POWER_PLAN_HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-e6f2ada34b1d"
$TOTAL = 10

# =====================================================================
# PYTHON BINARY RESOLVER — Windows = py.exe (Python Launcher for Windows) FIRST
#   Falls back: py > python3 > python. Fail friendly (never throw!).
# =====================================================================
Write-Host ''
Write-Host '--- PYTHON DETECTION DEBUG ---' -ForegroundColor Cyan
$script:py = $null
$candidates = @('py', 'python3', 'python', 'py.exe', 'python.exe', 'python3.exe')
foreach ($candidate in $candidates) {
    try {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            Write-Host ("  candidate [{0,-12}] FOUND at: {1}" -f $candidate, $cmd.Source)
            if (-not $script:py) {
                $script:py = $cmd.Source
            }
        } else {
            Write-Host ("  candidate [{0,-12}] NOT FOUND via Get-Command" -f $candidate)
        }
    } catch {
        Write-Host ("  candidate [{0,-12}] exception: {1}" -f $candidate, $_.Exception.Message)
    }
}

# Extra scan of common file-system locations (WindowsApps / Program Files / LocalAppData Programs Python)
$scanPaths = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "C:\Python312\python.exe",
    "C:\Python311\python.exe",
    "C:\Program Files\Python312\python.exe",
    "$env:LOCALAPPDATA\Microsoft\WindowsApps\py.exe"
)
foreach ($p in $scanPaths) {
    if (Test-Path $p) {
        Write-Host ("  filesystem scan FOUND: {0}" -f $p)
        if (-not $script:py) { $script:py = $p }
    }
}

if (-not $script:py) {
    Write-Banner 'FATAL: Python NOT FOUND in PATH or common install locations'
    Write-Host ''
    Write-Host '  Required: Python 3.12+. Install ONE of the following then re-run:'
    Write-Host ''
    Write-Host '  OPTION 1 (FASTEST ~2 min): WINGET (already confirmed working in STEP 1 above)'
    Write-Host '    PASTE IN ADMIN POWERSHELL:'
    Write-Host '      winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements'
    Write-Host ''
    Write-Host '  OPTION 2 (WEBSITE):'
    Write-Host '    Open https://www.python.org/downloads/'
    Write-Host '    Download Python 3.12.x for Windows -> Run installer'
    Write-Host '    ☑ CHECKBOX "Add Python 3.12 to PATH" MUST BE TICKED at BOTTOM of FIRST installer page'
    Write-Host '    After install finishes, REBOOT (PATH only fully refreshes on new logon)'
    Write-Host ''
    Write-Host '  To verify install worked, open NEW admin PowerShell and run:   py --version'
    Write-Host ''
    Read-Host 'Press ENTER to EXIT. Then install Python 3.12 and re-run.'
    exit 2
}
Write-Host ''
Write-Host ('  SELECTED Python bin : ' + $script:py) -ForegroundColor Green
try {
    $pv = & $script:py --version 2>&1
    Write-Host ('  Python version      : ' + $pv) -ForegroundColor Green
} catch {
    Write-Warn ('Python --version call failed non-fatal: ' + $_)
}
Write-Host '--- END PYTHON DEBUG ---' -ForegroundColor Cyan
Write-Host ''

New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

function Write-Step {
    param([int]$N,[string]$Msg,[ConsoleColor]$Color=[ConsoleColor]::Cyan)
    $stamp = Get-Date -Format "HH:mm:ss"
    $line = "[$stamp] [$N/$TOTAL] $Msg"
    Write-Host $line -ForegroundColor $Color
    Add-Content -Path $MASTER_LOG -Value $line
}
function Write-OK   { param($Msg) Write-Host "  [OK]   $Msg" -ForegroundColor Green; Add-Content $MASTER_LOG "  [OK]   $Msg" }
function Write-Warn { param($Msg) Write-Host "  [WARN] $Msg" -ForegroundColor Yellow; Add-Content $MASTER_LOG "  [WARN] $Msg" }
function Write-Fail { param($Msg) Write-Host "  [FAIL] $Msg" -ForegroundColor Red; Add-Content $MASTER_LOG "  [FAIL] $Msg" }
function Write-Banner {
    param($Title)
    $sep = "=" * 72
    $out = "`n$sep`n=== $Title`n$sep"
    Write-Host $out -ForegroundColor Magenta
    Add-Content $MASTER_LOG -Value $out
}

Write-Banner ('NOESIS W7 AUTORUN STARTED at ' + $TIMESTAMP)
Write-Host ('  Repo root  : ' + $REPO_ROOT)
Write-Host ('  Backend    : ' + $BACKEND_DIR)
Write-Host ('  Master log : ' + $MASTER_LOG)
Write-Host ('  Flags      : DryRunOnly=' + $DryRunOnly + '  SkipDeepSeek=' + $SkipDeepSeek + '  Suffix=' + $OutDirSuffix)
$Global:W7_MASTER_LOG_PATH = $MASTER_LOG

# ---------------------------------------------------------------------
# STEP 0/10 SELF-ELEVATE ADMIN
# ---------------------------------------------------------------------
Write-Step 0 'ADMIN SELF-ELEVATION'
$myId = [Security.Principal.WindowsIdentity]::GetCurrent()
$myPrincipal = New-Object Security.Principal.WindowsPrincipal($myId)
$isAdmin = $myPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warn "Not running as Admin. Restarting with elevation (UAC prompt will appear) ..."
    $argList = @("-ExecutionPolicy","Bypass","-NoProfile","-File",$MyInvocation.MyCommand.Path)
    if ($SkipDeepSeek)  { $argList += "-SkipDeepSeek" }
    if ($DryRunOnly)    { $argList += "-DryRunOnly" }
    if ($OutDirSuffix)  { $argList += "-OutDirSuffix"; $argList += $OutDirSuffix }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $argList
    exit 0
}
Write-OK "Running as ADMIN. UAC elevation complete."

# ---------------------------------------------------------------------
# STEP 1/10 DETECT WINGET (Microsoft Desktop App Installer)
#   4-TIER FALLBACK — EXACTLY what Dhruv debugged and confirmed working:
#   (a) existing winget.exe in PATH
#   (b) PATH-APPEND from App Installer InstallLocation registered via Store
#   (c) Add-AppxPackage existing registered AppX package
#   (d) DIRECT DOWNLOAD GitHub msixbundle v1.9 official release install
# ---------------------------------------------------------------------
Write-Step 1 'DETECT + INSTALL WINGET 4-TIER FALLBACK'
$winget_ok = $false
try {
    $wgv = & winget --version 2>&1
    if ($LASTEXITCODE -eq 0 -and $wgv) {
        Write-OK ('winget installed PATH: ' + $wgv)
        $winget_ok = $true
    }
} catch {}

if (-not $winget_ok) {
    $msg = 'winget not in PATH. FALLBACK B: Append DesktopAppInstaller InstallLocation to session PATH'
    Write-Warn $msg
    try {
        $pkgLoc = $null
        try {
            $pkgs = Get-AppxPackage -Name Microsoft.DesktopAppInstaller -AllUsers -ErrorAction SilentlyContinue
            if ($pkgs -and $pkgs.InstallLocation) {
                $pkgLoc = $pkgs.InstallLocation
            }
        } catch {}
        if ([string]::IsNullOrWhiteSpace($pkgLoc)) {
            try {
                $pkgsCur = Get-AppxPackage -Name Microsoft.DesktopAppInstaller -ErrorAction SilentlyContinue
                if ($pkgsCur -and $pkgsCur.InstallLocation) {
                    $pkgLoc = $pkgsCur.InstallLocation
                }
            } catch {}
        }
        if (-not [string]::IsNullOrWhiteSpace($pkgLoc)) {
            $locmsg = 'Appending InstallLocation to PATH: ' + $pkgLoc
            Write-Warn $locmsg
            $mp = [System.Environment]::GetEnvironmentVariable('Path','Machine')
            $up = [System.Environment]::GetEnvironmentVariable('Path','User')
            $env:PATH =  $mp + ';' + $up + ';' + $pkgLoc
            Start-Sleep -Milliseconds 800
            try {
                $wgv2 = & winget --version 2>&1
                if ($LASTEXITCODE -eq 0 -and $wgv2) {
                    Write-OK ('winget installed FALLBACK B (PATH-APPEND): ' + $wgv2)
                    $winget_ok = $true
                }
            } catch {}
        }
    } catch {}
}

# ---------------------------------------------------------------------
# FALLBACK C (was B): Add-AppxPackage register existing AppX if still needed
if (-not $winget_ok) {
    $msg = 'winget still missing. FALLBACK C: Add-AppxPackage register existing AppX manifest'
    Write-Warn $msg
    try {
        $pkg = Get-AppxPackage -Name Microsoft.DesktopAppInstaller -AllUsers -ErrorAction SilentlyContinue
        if ($pkg -and $pkg.PackageFullName) {
            $regmsg = 'Registering existing AppX: ' + $pkg.PackageFullName
            Write-Warn $regmsg
            $manifest = Join-Path $pkg.InstallLocation 'AppxManifest.xml'
            if (Test-Path $manifest) {
                Add-AppxPackage -DisableDevelopmentMode -Register $manifest -ErrorAction Stop
                Start-Sleep 8
            }
        }
    } catch {}
    try {
        $wgv = & winget --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $wgv) {
            $okmsg = 'winget installed AppX register: ' + $wgv
            Write-OK $okmsg
            $winget_ok = $true
        }
    } catch {}
}

if (-not $winget_ok) {
    $msg = 'Fallback C: DIRECT DOWNLOAD winget-cli msixbundle from GitHub OFFICIAL RELEASES'
    Write-Warn $msg
    $ProgressPreference = 'SilentlyContinue'
    try {
        $dlUrl = 'https://github.com/microsoft/winget-cli/releases/download/v1.9.10061/Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle'
        $dlPath = Join-Path $LOG_DIR 'Microsoft.DesktopAppInstaller_v1.9.10061.msixbundle'
        $msg3 = 'Downloading 400MB msixbundle from GitHub to: ' + $dlPath
        Write-Warn $msg3
        Invoke-WebRequest -Uri $dlUrl -OutFile $dlPath -UseBasicParsing -ErrorAction Stop
        $dlSz = (Get-Item $dlPath).Length
        if ($dlSz -gt 100MB) {
            Write-Warn 'Running Add-AppxPackage msixbundle now'
            Add-AppxPackage -Path $dlPath -ErrorAction Stop
            Start-Sleep 10
            $env:PATH = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')
            $wgv = & winget --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $wgv) {
                $okmsg = 'winget installed DIRECT DOWNLOAD: ' + $wgv
                Write-OK $okmsg
                $winget_ok = $true
            }
        }
    } catch {
        $msg2 = 'Fallback C failed: ' + $_.Exception.Message
        Write-Warn $msg2
    }
}

if (-not $winget_ok) {
    Write-Fail 'WINGET NOT INSTALLED after all 3 fallbacks. Pick MANUAL FIX OPTION A or B:'
    Write-Host ''
    Write-Host '  OPTION A  EASIEST 60 SEC  MICROSOFT STORE 1 CLICK:'
    Write-Host '    1. Open Microsoft Store app'
    Write-Host '    2. Search box: App Installer   Publisher: Microsoft Corporation'
    Write-Host '    3. Click GET or UPDATE'
    Write-Host '    4. After install: close window + DOUBLE-CLICK this script again'
    Write-Host ''
    Write-Host '  OPTION B  GEEK 30 SEC  PASTE 3 COMMANDS NEW ADMIN POWERSHELL:'
    Write-Host ''
    Write-Host '    $u = "https://github.com/microsoft/winget-cli/releases/download/v1.9.10061/Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle"'
    Write-Host '    $o = "$env:USERPROFILE\Downloads\DesktopAppInstaller.msixbundle"'
    Write-Host '    iwr $u -OutFile $o; Add-AppxPackage $o; winget --version'
    Write-Host ''
    Write-Host '    After version prints: close window + DOUBLE-CLICK this script again'
    Write-Host ''
    try { Start-Process 'ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1' } catch {}
    Read-Host 'Press ENTER to EXIT then re-run W7_AUTORUN_20261005.ps1'
    exit 11
}

# ---------------------------------------------------------------------
# STEP 2/10 WINGET INSTALL OLLAMA
# ---------------------------------------------------------------------
Write-Step 2 'WINGET INSTALL Ollama.Ollama'
$ollama_cli_ok = $false
try {
    $ollamaV = & ollama --version 2>&1
    if ($LASTEXITCODE -eq 0 -and $ollamaV) {
        Write-OK "ollama.exe already installed: $ollamaV"
        $ollama_cli_ok = $true
    }
} catch {}

if (-not $ollama_cli_ok) {
    Write-Warn 'Ollama not installed. Running: winget install Ollama.Ollama UAC prompt may appear'
    & winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements --silent 2>&1 |
        Tee-Object -FilePath $MASTER_LOG -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "winget install Ollama.Ollama FAILED exit=$LASTEXITCODE"
        Write-Host "  Opening browser fallback download page: https://ollama.com/download/windows"
        Start-Process "https://ollama.com/download/windows"
        Read-Host "Press ENTER to EXIT (run installer, then re-run this script)"
        exit 12
    }
    $env:PATH = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
    Start-Sleep 5
    try {
        $ollamaV = & ollama --version 2>&1
        if ($LASTEXITCODE -eq 0) { Write-OK "ollama installed: $ollamaV"; $ollama_cli_ok = $true }
    } catch {}
}

# ---------------------------------------------------------------------
# STEP 3/10: START OLLAMA SERVE (PERSISTENT BACKGROUND)
# ---------------------------------------------------------------------
Write-Step 3 'START OLLAMA SERVE BACKGROUND'
$pingOk = $false
$maxServeAttempt = 0
while (-not $pingOk -and $maxServeAttempt -lt 6) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iasync = $client.BeginConnect("127.0.0.1", 11434, $null, $null)
        $wait = $iasync.AsyncWaitHandle.WaitOne(1500, $false)
        if ($wait -and $client.Connected) { $pingOk = $true; $client.Close() }
    } catch {}
    if (-not $pingOk) {
        Write-Warn "ollama serve not reachable attempt $($maxServeAttempt+1)/6. Spawning hidden..."
        $soLog = Join-Path $LOG_DIR "ollama_serve_stdout_$TIMESTAMP.log"
        $seLog = Join-Path $LOG_DIR "ollama_serve_stderr_$TIMESTAMP.log"
        Start-Process -FilePath "ollama.exe" -ArgumentList "serve" `
            -WindowStyle Hidden `
            -RedirectStandardOutput $soLog `
            -RedirectStandardError $seLog
        Start-Sleep -12
    }
    $maxServeAttempt++
}
if (-not $pingOk) {
    Write-Fail "Could not start ollama serve on port 11434 after 6 attempts."
    Write-Host "  MANUAL FIX: open NEW admin PowerShell, paste: ollama serve"
    Write-Host "  Leave it running, then press ENTER to re-try this script"
    Read-Host "Press ENTER to EXIT"
    exit 13
}
Write-OK "ollama serve reachable on tcp://127.0.0.1:11434"

# ---------------------------------------------------------------------
# STEP 4/10 PULL PRIMARY MODEL 4.7 GB
# ---------------------------------------------------------------------
Write-Step 4 ('PULL PRIMARY MODEL: ' + $PRIMARY_MODEL + '  4.7 GB')
$needPrimary = $true
try {
    $list = (& ollama list 2>&1 | Out-String)
    if ($list -match [regex]::Escape($PRIMARY_MODEL)) {
        Write-OK "PRIMARY already present. Skipping pull."
        $needPrimary = $false
    }
} catch {}
if ($needPrimary) {
    Write-Warn "Pulling PRIMARY MODEL FIRST TIME = 10-60 minutes depending on internet speed"
    & ollama pull $PRIMARY_MODEL 2>&1 | Tee-Object -FilePath $MASTER_LOG -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "pull primary FAILED exit=$LASTEXITCODE"
        Read-Host "Press ENTER to EXIT"
        exit 14
    }
    Write-OK "PRIMARY MODEL pulled successfully"
}

# ---------------------------------------------------------------------
# STEP 5/10 PULL SECONDARY 9.4 GB OPTIONAL
# ---------------------------------------------------------------------
if ($SkipDeepSeek) {
    Write-Step 5 'SKIP SECONDARY MODEL  -SkipDeepSeek FLAG SET'
} else {
    Write-Step 5 ('PULL SECONDARY MODEL: ' + $SECONDARY_MODEL + '  9.4 GB OPTIONAL')
    $needSecondary = $true
    try {
        $list = (& ollama list 2>&1 | Out-String)
        if ($list -match [regex]::Escape($SECONDARY_MODEL)) {
            Write-OK "SECONDARY already present. Skipping pull."
            $needSecondary = $false
        }
    } catch {}
    if ($needSecondary) {
        Write-Warn "Pulling SECONDARY MODEL (skip with -SkipDeepSeek). 25-90 minutes."
        & ollama pull $SECONDARY_MODEL 2>&1 | Tee-Object -FilePath $MASTER_LOG -Append | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "SECONDARY pull FAILED exit=$LASTEXITCODE (non-fatal; harness falls back to qwen-only)"
        } else {
            Write-OK "SECONDARY MODEL pulled successfully"
        }
    }
}

# ---------------------------------------------------------------------
# STEP 6/10 POWERCFG HIGH PERFORMANCE
# ---------------------------------------------------------------------
Write-Step 6 'POWERCFG HIGH PERFORMANCE PLAN'
try {
    $planSet = $false
    $planMsg = ''
    # Alias SCHEME_MIN = High Performance power plan builtin ALL Windows versions (works when GUID differs from build to build)
    try {
        & powercfg /setactive SCHEME_MIN 2>&1 | Tee-Object -FilePath $MASTER_LOG -Append | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $planSet = $true
            $planMsg = 'SCHEME_MIN (builtin alias for High Performance)'
        }
    } catch {}
    if (-not $planSet) {
        # Fallback: explicit GUID from MS docs (works on most Pro/Enterprise installs)
        try {
            & powercfg /setactive $POWER_PLAN_HIGH_PERF 2>&1 | Tee-Object -FilePath $MASTER_LOG -Append | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $planSet = $true
                $planMsg = ('GUID=' + $POWER_PLAN_HIGH_PERF)
            }
        } catch {}
    }
    $curPlan = (& powercfg /getactivescheme 2>&1 | Out-String)
    if ($planSet -or ($curPlan -match "High" -or $curPlan -match "8c5e7fda" -or $curPlan -match "SCHEME_MIN")) {
        Write-OK ('Power plan = HIGH PERFORMANCE. ' + $planMsg + ' Output: ' + $curPlan.Trim())
    } else {
        Write-Warn ('powercfg exit. Fallback GUID also failed. Current plan output: ' + $curPlan)
    }
} catch { Write-Warn ('powercfg exception (non-fatal): ' + $_) }

# ---------------------------------------------------------------------
# STEP 7/10 PING GUARD CHECK MANDATORY EXIT 0 REQUIRED
# ---------------------------------------------------------------------
Write-Step 7 'OLLAMA PING GUARD EXIT 0 REQUIRED'
Push-Location $BACKEND_DIR
& $script:py scripts\ollama_ping.py 2>&1 | Tee-Object -FilePath $MASTER_LOG -Append | Out-Null
$pingExit = $LASTEXITCODE
Pop-Location
if ($pingExit -ne 0) {
    Write-Fail "PING GUARD FAILED exit=$pingExit (0 REQUIRED). Models missing or serve down?"
    Read-Host "Press ENTER to EXIT"
    exit 17
}
Write-OK "PING GUARD exit 0 - inference pipeline READY."

# ---------------------------------------------------------------------
# STEP 8/10 FULL BENCHMARK RUN 6-14 HOURS / DRY RUN 2 MIN
# ---------------------------------------------------------------------
if ($DryRunOnly) {
    Write-Step 8 'DRY RUN ONLY MockProvider SEEDED 2 MINUTES'
    $outArg = '..\docs\eval\w7_weekend_dryrun_auto_' + $TIMESTAMP
    Push-Location $BACKEND_DIR
    & $script:py scripts\run_w7_weekend.py --dry-run --seed 42 --outdir $outArg 2>&1 |
        Tee-Object -FilePath $MASTER_LOG -Append | Out-Null
    $runExit = $LASTEXITCODE
    Pop-Location
} else {
    Write-Step 8 ('FULL OVERNIGHT BENCHMARK START 6-14 HOURS 🔥')
    $eta = Get-Date -Date (Get-Date).AddHours(8) -Format 'yyyy-MM-dd HH:mm'
    Write-Warn ('Estimated completion: ~' + $eta)
    Write-Warn 'DO NOT CLOSE WINDOW - DO NOT SLEEP - PLUG IN LAPTOP CHARGER 🔌'
    $outArg = "..\docs\eval\w7_weekend_$OutDirSuffix"
    Push-Location $BACKEND_DIR
    & $script:py scripts\run_w7_weekend.py --full --seed 42 --outdir $outArg 2>&1 |
        Tee-Object -FilePath $MASTER_LOG -Append | Out-Null
    $runExit = $LASTEXITCODE
    Pop-Location
}
if ($runExit -ne 0) {
    Write-Fail "BENCHMARK HARNESS FAILED exit=$runExit"
    Write-Host "  Inspect logs in: $outArg\logs\step*.log"
    Read-Host "Press ENTER to EXIT"
    exit 18
}
Write-OK "BENCHMARK PIPELINE exit 0 - results saved to: docs\eval\$(Split-Path $outArg -Leaf)"

# ---------------------------------------------------------------------
# STEP 9/10 POST-PROCESS SWAP SMOKE -> REAL + THESIS REBUILD
# ---------------------------------------------------------------------
Write-Step 9 'POST-PROCESS MERGE CH06 INTO THESIS DOCX'
Push-Location $REPO_ROOT
try {
    & $script:py scripts\merge_ch6_into_thesis.py 2>&1 | Tee-Object -FilePath $MASTER_LOG -Append | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $docxPath = Join-Path $REPO_ROOT 'NOESIS_thesis_chapters_1_through_8_UPDATED_SKELETON.docx'
        if (Test-Path $docxPath) {
            $docx = Get-Item $docxPath
            $info = 'DOCX rebuilt OK size=' + $docx.Length + ' bytes - path: ' + $docxPath
            Write-OK $info
        }
    } else {
        Write-Warn ('merge_ch6 exit=' + $LASTEXITCODE + ' run manually later')
    }
} catch { Write-Warn ('merge exception: ' + $_) }
Pop-Location

# ---------------------------------------------------------------------
# STEP 10/10 DONE - SUMMARY + NOTIFICATION
# ---------------------------------------------------------------------
Write-Step 10 'W7 AUTORUN PIPELINE COMPLETE 🏆'
Write-Banner 'W7 AUTORUN FULLY COMPLETE DONE'
Write-Host ''
Write-Host ('  Master log     : ' + $MASTER_LOG)
Write-Host ('  Output dir     : ' + $outArg)
Write-Host '  Table snapshot : backend\docs\eval\tables_for_paper_LATEST.json'
Write-Host ''
Write-Host '  NEXT STEPS copy paste verify:'
Write-Host '  1 Bench Hub LIVE:'
$t1 = '     T1: cd backend; ' + $script:py + ' -m uvicorn noesis.api.main:app --reload --port 8000'
Write-Host $t1
Write-Host '     T2: cd frontend; $env:PATH = "$PWD\.node;$env:PATH"; .node\npm.cmd run dev'
Write-Host '     URL: http://localhost:3000/benchmarks'
Write-Host ''
Write-Host '  2 Commit and push results:'
Write-Host ('     git add docs/eval/w7_weekend_' + $OutDirSuffix)
Write-Host '     git add backend/docs/eval/tables_for_paper_LATEST.json'
Write-Host '     git commit -m "eval: W7 real numbers qwen ablation Oct05"'
Write-Host '     git push -u origin main'
Write-Host ''
Write-Host '  3 Record 14-min VIVA MP4:'
Write-Host '     OBS window capture Frontend narrate walkthrough_script.md'
Write-Host ''

# BEEP x3 audio alert
1..3 | ForEach-Object { [Console]::Beep(880, 400); Start-Sleep -Milliseconds 450 }

Write-Host ''
Write-Host '========================================================================' -ForegroundColor Green
Write-Host '=== ✅ W7 AUTORUN FULLY COMPLETED SUCCESSFULLY ===' -ForegroundColor Green
Write-Host '========================================================================' -ForegroundColor Green
Write-Host ''
Write-Host ('  Master log     : ' + $MASTER_LOG)
Write-Host ('  Output dir     : ' + $outArg)
Write-Host '  Table snapshot : backend\docs\eval\tables_for_paper_LATEST.json'
Write-Host ''
Read-Host 'Press ENTER to close this window - ollama serve remains running in tray'
exit 0
