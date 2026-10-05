# Release Checklist — Noesis v0.2.0-rc2

**Target date:** 2026-08-24
**Owner:** Dhruv Shah
**Artefacts produced:**
  - TestPyPI wheel: `noesis-0.2.0rc2-py3-none-any.whl` + sdist
  - Container image: `ghcr.io/dhruvshah11/noesis:0.2.0-rc2`
  - SBOM: `dist/noesis-sbom.spdx.json` (SPDX 2.3 JSON, syft-generated)
  - GitHub Release draft: `v0.2.0-rc2` with wheel + SBOM attachments
  - Frontend: `frontend/.next/export/` (standalone static export)

---

## 15-Step Ordered Release Procedure

### 01. `git init` + first commit with `.gitignore`
```powershell
cd c:\Users\dhruv\Downloads\ASTRAOS
git init
git checkout -b main
git add -A
git status
git commit -m "chore: initial import for v0.2.0-rc2
- MS9 selfhost 10-PR benchmark skeleton
- MS10 SBOM + Docker laptop + RC2 packaging + changelog"
```
✅ Confirm: `git log --oneline -1` shows the commit.

### 02. GitHub CLI auth + create private repo
```powershell
gh auth login
# (browser flow, select GitHub.com, SSO if org-owned)
gh repo create dhruvshah11/noesis --private --source . --remote origin --push
```
✅ Confirm: `gh repo view dhruvshah11/noesis` returns metadata.

### 03. Install release tooling (twine)
```powershell
cd backend
py -m pip install --upgrade pip setuptools wheel twine hatchling build
```
✅ Confirm: `py -m twine --version` ≥ 5.0.

### 04. `hatch build clean` → reproducible wheel + sdist
```powershell
cd backend
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }
Get-ChildItem -Recurse -Filter *.egg-info | Remove-Item -Recurse -Force
py -m build
Get-ChildItem dist\
```
✅ Confirm: `dist\noesis-0.2.0rc2-py3-none-any.whl` + `noesis-0.2.0rc2.tar.gz` exist.
✅ Confirm: wheel size is between 400 KB and 3 MB (sanity check — excludes benchmarks).

### 05. `twine upload --repository testpypi dist/*`
```powershell
cd backend
py -m twine upload --repository testpypi --non-interactive --username __token__ --password $env:TESTPYPI_TOKEN dist\*
```
✅ Confirm: `https://test.pypi.org/project/noesis/0.2.0rc2/` opens and shows files.

### 06. Install from TestPyPI + smoke test
```powershell
# Use a clean throwaway venv for smoke
py -m venv $env:TEMP\noesis_smoke_venv
& $env:TEMP\noesis_smoke_venv\Scripts\Activate.ps1
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ noesis==0.2.0rc2
python -c "import noesis; from noesis.api.main import create_app; app = create_app(); print('noesis smoke ok, app routes =', len(app.routes))"
deactivate
Remove-Item -Recurse -Force $env:TEMP\noesis_smoke_venv
```
✅ Confirm: `noesis smoke ok, app routes = …` prints without import errors.

### 07. Signed git tag `v0.2.0-rc2`
```powershell
# Requires GPG key configured via `git config --global user.signingkey <KEYID>`
git tag -s -u <KEYID> v0.2.0-rc2 -m "Noesis v0.2.0-rc2 — MS9 selfhost 10-PR + MS10 SBOM/RC2 packaging"
git verify-tag v0.2.0-rc2
git push origin v0.2.0-rc2
```
✅ Confirm: `gh api repos/dhruvshah11/noesis/git/refs/tags/v0.2.0-rc2` returns the signed object.

### 08. Draft GitHub Release with wheel + SBOM attachments
```powershell
# First run the SBOM audit locally so dist/noesis-sbom.spdx.json exists:
cd backend
.\scripts\audit_sbom.ps1    # Produces dist/noesis-sbom.spdx.json ; confirms Trivy 0 HIGH/CRITICAL

gh release create v0.2.0-rc2 `
  --draft `
  --title "Noesis v0.2.0-rc2 — MS9 Self-Host + MS10 RC2 Packaging" `
  --notes-file backend\CHANGELOG.md `
  --target main `
  backend\dist\noesis-0.2.0rc2-py3-none-any.whl `
  backend\dist\noesis-0.2.0rc2.tar.gz `
  backend\dist\noesis-sbom.spdx.json
```
✅ Confirm: `gh release view v0.2.0-rc2` lists 3 assets.

### 09. Docker build + push to `ghcr.io/dhruvshah11/noesis:0.2.0-rc2`
```powershell
cd backend
docker build -f Dockerfile.laptop -t local/noesis:0.2.0-rc2 .
docker tag local/noesis:0.2.0-rc2 ghcr.io/dhruvshah11/noesis:0.2.0-rc2
echo $env:GITHUB_TOKEN | docker login ghcr.io -u dhruvshah11 --password-stdin
docker push ghcr.io/dhruvshah11/noesis:0.2.0-rc2
```
✅ Confirm: `gh api user/packages/container/noesis/versions` lists tag `0.2.0-rc2`.

### 10. Trivy 0 HIGH/CRITICAL verify on the *pushed* image
```powershell
trivy image --severity HIGH,CRITICAL --exit-code 1 --no-progress `
  --ignorefile backend\sbom\trivyignore `
  ghcr.io/dhruvshah11/noesis:0.2.0-rc2
```
✅ Confirm: exit code 0, no HIGH or CRITICAL rows printed.

### 11. Run all 4 audits via `run_all_audits.ps1`
```powershell
cd backend
.\docs\eval\run_all_audits.ps1
```
✅ Confirm: exit code 0.  Expected sub-exit codes:
  - (a) `audit_mac_spawn.py` → 0
  - (b) `determinism_manifest.py --runs 5 --seeds 42` → 0, CSV written
  - (c) `audit_llm_providers.py` → 0
  - (d) memory promotion placeholder → 0

### 12. Vercel / Hetzner deploy backend smoke
```powershell
# Option A — Vercel (serverless functions):
cd backend
vercel --prod --yes
# (wait for deploy URL; then:)
curl -f https://<DEPLOY_URL>/api/health

# Option B — Hetzner cloud VM with docker:
#   scp -i ~/.ssh/hetzner docker-compose.laptop.yml user@<IP>:/opt/noesis/
#   ssh user@<IP> "cd /opt/noesis && docker compose -f docker-compose.laptop.yml up -d"
#   curl -f http://<IP>:8000/health
```
✅ Confirm: `/health` returns 200 with `"status": "pass"`.

### 13. Frontend `npm run build` + standalone export
```powershell
cd frontend
# If first run on this machine:
# npm install --no-audit --no-fund
npm run build
npm run export
Get-ChildItem .next\export\
# Spot-check the exported index size > 20 KB
```
✅ Confirm: `frontend/.next/export/index.html` exists and references `/next/static/` assets.

### 14. 30-minute soak test with `?demo=true` + 5 SE50 tasks
Launch 2 browser windows side-by-side:
  1. Backend API server locally OR the Vercel/Hetzner URL from step 12.
  2. Frontend at `http://localhost:3000/?demo=true` (or the exported frontend behind any static HTTP server).

Kick off 5 SE50 tasks from the corpus via the new-task UI (or `/v1/tasks` POST).
Expected observations after 30 minutes:
  - 5 task rows visible on `/timeline`, each with a Kriyakārī tristate decision.
  - No 5xx spiking in `GET /metrics` (Prometheus `http_requests_total{status=~"5.."}` delta ≤ 2).
  - Memory promotion controller has run at least one tick (`noesis_memory_promotion_ticks_total` ≥ 1).
  - Backend RSS stays under 1.5 GB, frontend tab heap under 400 MB.

✅ Confirm: screenshot the timeline page to `docs/eval/soak_rc2_30min.png`.

### 15. Tweet/X + LinkedIn + Discord (university server) announcement
Post the announcement simultaneously across all 3 channels.  Suggested copy:
```
🚀 Noesis v0.2.0-rc2 is live!
Milestones MS9 (Self-Host 10-PR Benchmark) + MS10 (SBOM + RC2 packaging).

Highlights:
▸ 12-agent Sanskrit-named seeded pipeline
▸ 3-stage Docker laptop image (non-root uid 10001, HEALTHCHECK /health)
▸ SPDX 2.3 SBOM + Trivy 0 HIGH/CRITICAL gate
▸ Determinism C3 (1.0 reproducibility) + MAC 4-deny-scenario audit
▸ Paper/thesis drafts: docs/paper + docs/thesis/chapters 01..08

GitHub Release: https://github.com/dhruvshah11/noesis/releases/tag/v0.2.0-rc2
TestPyPI:       https://test.pypi.org/project/noesis/0.2.0rc2/
Container:      ghcr.io/dhruvshah11/noesis:0.2.0-rc2

#Noesis #MultiAgentAI #OperatingSystemsForAI #RAG #SBOM #Determinism
```
✅ Confirm: 3 URLs pasted into a comment on the `v0.2.0-rc2` Release draft.

---

## Post-Step-15 — Promote from draft → published
Once steps 1–15 are all ✅ on the RC2 candidate AND the soak test shows no
regression, flip the GitHub Release `v0.2.0-rc2` from **Draft → Publish**.
Then re-run step 05 against **main PyPI** (drop `--repository testpypi`) to
ship the final `0.2.0` wheel without recompilation.

### Failure protocol
If any step 10–14 fails with a regression:
1. Open a GitHub Issue titled `RC2 BLOCKER: <summary>`.
2. Fix on a branch `hotfix/rc2-<N>`, PR to `main`, get 1 review.
3. Bump version string `0.2.0-rc2` → `0.2.0-rc3` in:
   - `backend/pyproject.toml` → `[project] version`
   - `backend/Dockerfile.laptop` → `org.opencontainers.image.version` label
   - This checklist → rename file + update references
4. Restart the checklist from step 04.
