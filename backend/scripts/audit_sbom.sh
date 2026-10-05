#!/usr/bin/env bash
# =====================================================================
# Noesis SBOM Audit Script (Bash / macOS / Linux / WSL)
# MS9 deliverable — run from backend/ directory.
#
#   cd backend ; bash scripts/audit_sbom.sh
#
# Steps:
#   1. Install syft + trivy (optional — see commented scoop/choco/apt lines
#      below for your platform; if already installed, skip straight to
#      scanning).
#   2. Generate SPDX-JSON SBOM of the laptop Dockerfile into dist/.
#   3. Run Trivy image scan against local/noesis:0.2.0-rc2 with
#      --severity HIGH,CRITICAL --exit-code 1.
#
# Exit codes:
#   0  SBOM generated + 0 HIGH/CRITICAL findings.
#   1  Trivy found at least one HIGH or CRITICAL vulnerability.
#   2  Missing prerequisite (docker, syft, or trivy not on PATH).
# =====================================================================

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${BACKEND_DIR}/dist"
IMAGE_TAG="local/noesis:0.2.0-rc2"
SBOM_OUT="${DIST_DIR}/noesis-sbom.spdx.json"
TRIVYIGNORE="${BACKEND_DIR}/sbom/trivyignore"

log()  { printf '[audit_sbom] %s\n' "$*"; }
warn() { printf '[audit_sbom][WARN] %s\n' "$*" >&2; }
err()  { printf '[audit_sbom][ERR ] %s\n' "$*" >&2; }

mkdir -p "${DIST_DIR}"

# -------------------------------------------------------------------
# Prerequisite checks
# -------------------------------------------------------------------
need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        err "missing prerequisite: '$1' not found on PATH."
        warn "Install hints (uncomment one block for your platform at the top of this script, or run manually):"
        warn "  macOS (homebrew):  brew install syft trivy"
        warn "  Debian/Ubuntu:     sudo apt install -y syft trivy   # or use install scripts below"
        warn "  Arch:              yay -S syft trivy-bin"
        return 1
    fi
    return 0
}

need_cmd docker || exit 2
need_cmd syft   || exit 2
need_cmd trivy  || exit 2

# -------------------------------------------------------------------
# Optional: one-line installers (kept commented — user opts in)
# -------------------------------------------------------------------
# curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
# curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# -------------------------------------------------------------------
# Step 1 — ensure the image is built locally
# -------------------------------------------------------------------
if ! docker image inspect "${IMAGE_TAG}" >/dev/null 2>&1; then
    log "Image ${IMAGE_TAG} not found locally — running docker build now."
    (cd "${BACKEND_DIR}" && docker build -f Dockerfile.laptop -t "${IMAGE_TAG}" .)
fi

# -------------------------------------------------------------------
# Step 2 — syft SBOM (SPDX-JSON) into dist/
# -------------------------------------------------------------------
log "Generating SPDX-JSON SBOM via syft -> ${SBOM_OUT}"
syft packages "${BACKEND_DIR}/Dockerfile.laptop" \
    -o spdx-json="${SBOM_OUT}" \
    --quiet

if [ ! -s "${SBOM_OUT}" ]; then
    err "SBOM output is empty or missing at ${SBOM_OUT}"
    exit 2
fi
SBOM_SIZE=$(wc -c < "${SBOM_OUT}" | tr -d ' ')
log "SBOM written: ${SBOM_OUT} (${SBOM_SIZE} bytes)"

# -------------------------------------------------------------------
# Step 3 — Trivy HIGH/CRITICAL scan with exit-code 1 gating
# -------------------------------------------------------------------
log "Running Trivy image scan (HIGH + CRITICAL only, gated)..."
if trivy image \
    --severity HIGH,CRITICAL \
    --exit-code 1 \
    --no-progress \
    --ignorefile "${TRIVYIGNORE}" \
    "${IMAGE_TAG}"; then
    log "Trivy scan: PASS (0 HIGH / 0 CRITICAL findings)."
else
    rc=$?
    err "Trivy scan: FAIL (exit ${rc}). Fix vulnerabilities above, then re-run."
    exit "${rc}"
fi

log "SBOM audit complete."
exit 0
