# Docker + SBOM RC2 Real Audit Playbook (Laptop-First, 60-90 min First Time)
## Environment Evidence (2026-10-05 Dhruv Laptop)
```
[FAIL] docker command   = 'docker' term not found in PATH → Docker Desktop not installed or not launched
[FAIL] winget command   = not found in sandbox PATH (installer uses Windows native winget, run on YOUR actual PowerShell - not sandboxed)
[SKIP] Syft (Anchore)   = not verified (winget missing)
[SKIP] Trivy (AquaSec)  = not verified (winget missing)
[OK]   audit_sbom.ps1   = exists c:\Users\dhruv\Downloads\ASTRAOS\audit_sbom.ps1 (781 lines, 7-step parity dry-run exit 0 verified 2026-08-26)
[OK]   audit_sbom.sh    = exists c:\Users\dhruv\Downloads\ASTRAOS\audit_sbom.sh (1,241 lines — WSL fallback if PS fails)
[OK]   Dockerfile.laptop= exists c:\Users\dhruv\Downloads\ASTRAOS\Dockerfile.laptop (RC2 production laptop image)
[OK]   dist/ folder     = already exists as gitignored staging area for SBOM outputs
```

## Action Plan — 5 Stages (copy-paste commands into your actual PowerShell admin terminal NOT SANDBOX)

### Stage 1: Install Docker Desktop (Windows 11 / 10 — 10 min)
Download + install exe from official docker.com (NOT winget for docker desktop, official exe more reliable):
1. URL: https://www.docker.com/products/docker-desktop/ → Download for Windows x86_64 (≈680 MB)
2. Run installer "Docker Desktop Installer.exe" → checkboxes: ☑ Use WSL 2 instead of Hyper-V (RECOMMENDED) ☑ Add shortcut to desktop
3. Install completes. REBOOT COMPUTER (mandatory — Docker adds WSL2 kernel components that require reboot. If you skip reboot, Stage 2 docker daemon fails permanently until you reboot).
4. Post reboot → Desktop shortcut Docker → Start → Accept Terms → You may see a popup that says "WSL 2 installation is incomplete". Follow the popup link: `https://aka.ms/wsl2kernel` → download WSL2 Linux kernel update package msi → install → OK.
5. Docker Desktop tray bottom-right icon = WHALE ICON turns GREEN (not amber not red). Wait 90s after it turns green (daemon warmup).
6. VERIFY STAGE 1 SUCCESS → Open NEW regular PowerShell (NOT admin) → run: `docker ps`
Expected output = empty table header:
```
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
```
(empty list is OK. The important part is that the command runs without "docker term not found"). If you get error "Docker daemon not running" → Docker Desktop isn't fully started yet, wait 30s, try again.

### Stage 2: Install Syft + Trivy (winget 2 packages, 2 min)
Open elevated ADMIN PowerShell (right-click start, Windows PowerShell (Admin) → Yes UAC prompt).
```powershell
# Step 2a: Verify winget exists (ships preinstalled Windows 11 — if it says not found, install "App Installer" from Microsoft Store)
winget --version
# Expected output = v1.7+ or similar

# Step 2b: Install Anchore Syft (SPDX + CycloneDX generator)
winget install --id Anchore.Syft -e --accept-package-agreements --accept-source-agreements

# Step 2c: Install Aqua Security Trivy (CVE vulnerability scanner)
winget install --id AquaSecurity.Trivy -e --accept-package-agreements --accept-source-agreements
```
Close Admin shell, open NEW regular PowerShell so PATH refreshes. Verify:
```powershell
syft version
trivy --version
```
Both commands should print version numbers (Syft 0.x, Trivy 0.x). If not you need to logout/login Windows.

### Stage 3: First Full RC2 Audit Run (expect 40-70 minutes)
Dhruv: run from your actual c:\Users\dhruv\Downloads\ASTRAOS in a regular PowerShell.
```powershell
cd c:\Users\dhruv\Downloads\ASTRAOS
.\audit_sbom.ps1 -Mode REAL
```
What the script does (auto — no user prompts):
```
SBOM_STEP_1_ENVIRONMENT   → runs docker info; syft version; trivy version
SBOM_STEP_2_DOCKER_BUILD  → docker build -f Dockerfile.laptop -t noesis:rc2 . (LONG: pulls python:3.12-slim base image ≈ 120 MB + npm install + pip install 5-30 min depending internet speed)
SBOM_STEP_3_SYFT_SBOM_JSON → syft packages noesis:rc2 -o spdx-json=./dist/sbom/rc2/sbom.spdx.json
SBOM_STEP_4_SYFT_SBOM_CYCLONEDX → syft packages noesis:rc2 -o cyclonedx-xml=./dist/sbom/rc2/sbom.cyclonedx.xml
SBOM_STEP_5_TRIVY_IMAGE_VULN → trivy image --severity CRITICAL,HIGH noesis:rc2 -f json -o ./dist/sbom/rc2/vuln-image.json  (FIRST RUN downloads CVE vulnerability DBs total ≈ 400-800 MB; 1-5 min on 50 Mbps)
SBOM_STEP_6_TRIVY_FS_VULN  → trivy fs ./ --severity CRITICAL,HIGH -f json -o ./dist/sbom/rc2/vuln-fs.json
SBOM_STEP_7_FINAL_SIGNATURE → reads 6 output files; computes sha256; appends HMAC signature; writes ./dist/sbom/rc2/audit_report_signed.json
```
Progress estimate breakdown 50 min total (first-time run):
  - Step 2 Docker build 35 min (slowest).
  - Step 5 Trivy DB download 10 min.
  - Other steps = ~5 min combined.

### Stage 4: Output Verification (post-run) — 6 Files MUST Exist
Run commands (PowerShell):
```powershell
Get-ChildItem c:\Users\dhruv\Downloads\ASTRAOS\dist\sbom\rc2\ -Name
```
EXPECTED OUTPUT LIST (6 files exactly — first 5 data + last 1 signed aggregate):
```
sbom.spdx.json         ← Anchore Syft SPDX 2.3 JSON (≈ 200-800 KB)
sbom.cyclonedx.xml     ← OWASP CycloneDX 1.5 XML (≈ 150-400 KB)
vuln-image.json        ← Trivy image scan — CRITICAL + HIGH findings (≈ 30-200 KB)
vuln-fs.json           ← Trivy filesystem scan — CRITICAL + HIGH findings (≈ 20-150 KB)
*.docker.build.log.txt ← (optional) build stdout log if script saves it
audit_report_signed.json ← FINAL SIGNED aggregate report with HMAC-SHA256 signature (small file)
```
OPEN audit_report_signed.json in VSCode. Expected JSON schema top-level keys:
```json
{
  "audit_version": "0.2.0-rc2",
  "audit_date_utc":   "<ISO8601 timestamp>",
  "steps_total": 7,
  "steps_passed": 7,
  "steps_failed": 0,
  "rc2_signoff_confidence": 0.9261,
  "threshold_required_gte": 0.90,
  "signoff": "PASS",
  "artifact_sha256": "<64 hex chars>",
  "hmac_signature_b64url": "<long string>",
  "findings_critical_high": 0
}
```
If signoff says FAIL or findings_critical_high > 0 → read triage section below.

### Stage 5: Evidence Upload Attachments (Viva + CODS-COMAD)
Zip all 5 evidence files (skip build log) → `rc2_sbom_evidence_dhruv.zip`
Attach / upload to:
  (a) UPES Viva evidence repository share (OneDrive / Google Drive shared folder)
  (b) CODS-COMAD 2027 portal Supplementary Materials section
  (c) Email to Dr. Archana as "RC2 SBOM Audit Passed" followup with PDF zipped link.

## Triage Failures (Fail or C/H > 0)
| Symptom | Root Cause | Fix Step |
|---|---|---|
| Step 2 FAIL "unable to resolve python:3.12-slim" | Internet not connected or corporate firewall blocks DockerHub | Disable VPN temporarily; or in Docker Desktop → Settings → Resources → Proxies set manual proxy |
| Step 3 FAIL "syft manifest fetch docker: could not read container" | Docker image noesis:rc2 not built (Step 2 failed silently) | Fix Step 2 docker build errors first; `docker images | findstr noesis` should show rc2 tag |
| Step 5 FAIL "trivy: failed to download vulnerability DB: 429 Too Many Requests" | Aqua Security rate limit hit (run > 10/day public bucket) | Wait 60 min re-run; or add TRIVY_DB_REPOSITORY env to GHCR mirror |
| signoff FAIL "rc2_signoff_confidence 0.84 < 0.90" | C/H > 3 in vuln-image.json CVE table | Open vuln-image.json → $.Results[].Vulnerabilities → all Critical/High CVE IDs → run `pip install <package>==latest -e backend[security]` to upgrade pypi deps; re-run audit_sbom.ps1 |
| Windows Defender blocks PowerShell script (ExecutionPolicy Restricted) → script fails to start | Group Policy blocks unsigned .ps1 execution | Run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force` (only applies to the one current PowerShell window you have open; no machine-wide change). Then re-run .\audit_sbom.ps1 -Mode REAL |

## Appendix: Manual SBOM Inventory (For Triage Reference While Docker Not Installed)
Table of known components (same info as docs/eval/sbom_rc2_audit.md §1):
| Layer | Components |
|---|---|
| Backend | FastAPI 0.110+, Pydantic 2.8+, Python 3.12, python-multipart 0.0.32, prometheus_client 0.26.0, SQLAlchemy 2.x, bcrypt 4.x, PyJWT 2.x, cryptography 42.x, uvicorn 0.30, pytest 8.x, ruff 0.7.x |
| Frontend | Next.js 14.2.18, React 18, TypeScript 5.6.3 strict, Tailwindcss 3.4, TanStack Query 5, Recharts 2.13, lucide-react 0.454, sonner 2.0, zod 3.23, clsx 2.1, tailwind-merge 2.5, Vitest 2.1, ESLint 9 |
| Security Gate | C1 HMAC-SHA256 5-stage validation (split / MAC compare / Pydantic / TTL / caps+deny), 309 backend tests, 105 frontend tests, 8 claim-suites |
| 6 Memory Tiers | Indriya / Kushalata / Gyān / Ranniti / Yojanā / Tattva; 6 promotion rules, C3 determinism 450×3 SHA-256 identity |
| Container | Dockerfile.laptop python-slim; docker-compose.laptop.yml 4 services; potential targets: distroless python312 base (future work) |
