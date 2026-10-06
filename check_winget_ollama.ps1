$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

Write-Host "=== [1/4] WINGET.EXE IN PATH ===" -ForegroundColor Cyan
try {
    $wgv = & winget --version 2>&1
    $exitwinget = $LASTEXITCODE
    if ($exitwinget -eq 0 -and $wgv) {
        Write-Host "FOUND winget.exe version: $wgv" -ForegroundColor Green
    } else {
        Write-Host "NOT IN PATH exit=${exitwinget} text=${wgv}" -ForegroundColor Yellow
    }
} catch {
    $m = $_.Exception.Message
    Write-Host "NOT found in PATH: $m" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== [2/4] APPX REGISTERED Microsoft.DesktopAppInstaller ===" -ForegroundColor Cyan
try {
    $pkg = Get-AppxPackage -Name Microsoft.DesktopAppInstaller -AllUsers -ErrorAction SilentlyContinue
    if ($pkg) {
        Write-Host "FOUND AppX Name: $($pkg.Name)" -ForegroundColor Green
        Write-Host "FOUND AppX FullName: $($pkg.PackageFullName)" -ForegroundColor Green
        Write-Host "FOUND AppX Version: $($pkg.Version)" -ForegroundColor Green
        Write-Host "FOUND AppX InstallLoc: $($pkg.InstallLocation)" -ForegroundColor Green
    } else {
        Write-Host "NOT Registered AppX (Get-AppxPackage empty)" -ForegroundColor Red
    }
} catch {
    $m2 = $_.Exception.Message
    Write-Host "AppX query error: $m2" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== [3/4] PARTIAL MSIX DOWNLOAD in Downloads ===" -ForegroundColor Cyan
$dlPath = Join-Path $env:USERPROFILE "Downloads\DesktopAppInstaller.msixbundle"
if (Test-Path $dlPath) {
    $sz = (Get-Item $dlPath).Length
    $szMB = [math]::Round($sz / 1MB, 1)
    Write-Host "FOUND file size=$sz bytes ($szMB MB)" -ForegroundColor Yellow
    if ($sz -gt 100MB) {
        Write-Host "SIZE OK 100MB plus - Add-AppxPackage on this file works!" -ForegroundColor Green
    } else {
        $smallMB = $szMB
        Write-Host "SIZE TOO SMALL less than 100MB ($smallMB MB) - download interrupted, delete retry" -ForegroundColor Red
    }
} else {
    Write-Host "MSIX file NOT found in Downloads" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "=== [4/4] OLLAMA STATUS ===" -ForegroundColor Cyan
try {
    $ollv = & ollama --version 2>&1
    $exitcode = $LASTEXITCODE
    if ($exitcode -eq 0) {
        Write-Host "FOUND ollama.exe installed version: $ollv" -ForegroundColor Green
    } else {
        Write-Host "Ollama exit=${exitcode}: $ollv" -ForegroundColor Yellow
    }
} catch {
    $m3 = $_.Exception.Message
    Write-Host "NOT installed: $m3" -ForegroundColor Red
}
$tcpOK = $false
try {
    $cli = New-Object System.Net.Sockets.TcpClient
    $iact = $cli.BeginConnect("127.0.0.1", 11434, $null, $null)
    $wh = $iact.AsyncWaitHandle.WaitOne(1200, $false)
    if ($wh -and $cli.Connected) {
        $tcpOK = $true
        $cli.Close()
    }
} catch {}
if ($tcpOK) {
    Write-Host "FOUND ollama serve RUNNING on 127.0.0.1:11434" -ForegroundColor Green
} else {
    Write-Host "ollama serve NOT on 11434" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "=== FINAL SUMMARY ===" -ForegroundColor Magenta
Write-Host ""
