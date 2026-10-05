#!/usr/bin/env bash
# =====================================================================
# NOESIS RC2 SBOM+CVE Audit (Jetson/Linux parity — step 10/15)
# Bash 4+ — Jetson / Ubuntu / WSL
# =====================================================================

set -uo pipefail

DRY_RUN=0
SKIP_DOCKER_BUILD=0
SKIP_SYFT=0
SKIP_TRIVY=0
DOCKERFILE="./backend/Dockerfile.laptop"
IMAGE_TAG="noesis:0.2.0-rc2-laptop"
OUTPUT_DIR="./docs/eval/sbom_rc2"
WARNINGS=0
EXIT_CODE=0
DRY_RUN_COMMANDS_FILE=""
declare -a DRY_STEP_DESC=()
declare -a DRY_STEP_CMD=()
declare -a DRY_STEP_EXPECTED=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)          DRY_RUN=1; shift ;;
        --skip-docker-build) SKIP_DOCKER_BUILD=1; shift ;;
        --skip-syft)         SKIP_SYFT=1; shift ;;
        --skip-trivy)        SKIP_TRIVY=1; shift ;;
        --dockerfile)       DOCKERFILE="$2"; shift 2 ;;
        --image-tag)        IMAGE_TAG="$2"; shift 2 ;;
        --output-dir)       OUTPUT_DIR="$2"; shift 2 ;;
        -h|--help)
            cat <<EOF
Usage: $0 [OPTIONS]
  --dry-run              Print commands only, do not execute
  --skip-docker-build    Skip docker build step
  --skip-syft            Skip syft SBOM generation
  --skip-trivy           Skip trivy CVE scan
  --dockerfile PATH      Path to Dockerfile (default: ./backend/Dockerfile.laptop)
  --image-tag TAG        Image tag (default: noesis:0.2.0-rc2-laptop)
  --output-dir DIR       Output directory (default: ./docs/eval/sbom_rc2)
EOF
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 3 ;;
    esac
done

write_banner() {
    printf '\e[36m================================================================\e[0m\n'
    printf '\e[36m  NOESIS RC2 SBOM+CVE Audit (W10 Release Checklist step 10/15)\e[0m\n'
    printf '\e[36m================================================================\e[0m\n'
    printf '\n'
}

log()    { printf '[audit_sbom] %s\n' "$*"; }
ok()     { printf '\e[32m[audit_sbom][OK ]\e[0m %s\n' "$*"; }
warn()   { printf '\e[33m[audit_sbom][WARN]\e[0m %s\n' "$*" >&2; WARNINGS=$((WARNINGS + 1)); }
err()    { printf '\e[31m[audit_sbom][ERR ]\e[0m %s\n' "$*" >&2; }
dry()    { printf '\e[35m[audit_sbom][DRY ]\e[0m %s\n' "$*"; }

test_cmd() {
    command -v "$1" >/dev/null 2>&1
}

add_dry_run() {
    local desc="$1" cmd="$2" expected="$3"
    DRY_STEP_DESC+=("$desc")
    DRY_STEP_CMD+=("$cmd")
    DRY_STEP_EXPECTED+=("$expected")
}

write_banner

# -------------------------------------------------------------------
# Resolve output directory
# -------------------------------------------------------------------
OUTPUT_DIR="$(cd "$(dirname "$OUTPUT_DIR")" 2>/dev/null && pwd)/$(basename "$OUTPUT_DIR")" || true
log "Output directory: ${OUTPUT_DIR}"

if [[ ! -d "$OUTPUT_DIR" ]]; then
    if [[ $DRY_RUN -eq 1 ]]; then
        add_dry_run "Create output directory" "mkdir -p '${OUTPUT_DIR}'" "${OUTPUT_DIR}"
        dry "Would create directory: ${OUTPUT_DIR}"
    else
        mkdir -p "$OUTPUT_DIR"
        ok "Created directory: ${OUTPUT_DIR}"
    fi
fi

# -------------------------------------------------------------------
# Step 1: Verify Docker CLI
# -------------------------------------------------------------------
printf '\n'
log "--- Step 1: Verify Docker CLI ---"

DOCKER_OK=0
if [[ $SKIP_DOCKER_BUILD -eq 0 ]]; then
    if test_cmd docker; then
        if [[ $DRY_RUN -eq 1 ]]; then
            VER_CMD="docker --version"
            add_dry_run "Verify Docker CLI" "$VER_CMD" ""
            dry "Would run: ${VER_CMD}"
            DOCKER_OK=1
        else
            if ver=$(docker --version 2>&1); then
                ok "Docker found: ${ver}"
                DOCKER_OK=1
            else
                warn "docker --version returned non-zero"
            fi
        fi
    fi
    if [[ $DOCKER_OK -eq 0 ]]; then
        warn "Docker CLI not found — auto-setting SkipDockerBuild=1"
        SKIP_DOCKER_BUILD=1
    fi
else
    log "skip-docker-build set — skipping Docker CLI check"
fi

# -------------------------------------------------------------------
# Step 2: Docker build
# -------------------------------------------------------------------
printf '\n'
log "--- Step 2: Docker build (3-stage) ---"

if [[ $SKIP_DOCKER_BUILD -eq 0 ]]; then
    DOCKERFILE_FULL="$(cd "$(dirname "$DOCKERFILE")" 2>/dev/null && pwd)/$(basename "$DOCKERFILE")" || true
    BUILD_CONTEXT="$(dirname "$DOCKERFILE_FULL")"
    BUILD_CMD="docker build -f '${DOCKERFILE_FULL}' -t ${IMAGE_TAG} '${BUILD_CONTEXT}'"

    if [[ $DRY_RUN -eq 1 ]]; then
        add_dry_run "Docker 3-stage build" "$BUILD_CMD" "Local image: ${IMAGE_TAG}"
        dry "Would run: ${BUILD_CMD}"
    else
        if [[ ! -f "$DOCKERFILE_FULL" ]]; then
            err "Dockerfile not found: ${DOCKERFILE_FULL}"
            exit 2
        fi
        log "Running docker build: ${BUILD_CMD}"
        old_pwd="$PWD"
        cd "$BUILD_CONTEXT"
        if docker build -f "$DOCKERFILE_FULL" -t "$IMAGE_TAG" .; then
            ok "Docker build succeeded: ${IMAGE_TAG}"
        else
            rc=$?
            err "docker build FAILED (exit ${rc})"
            cd "$old_pwd"
            exit 2
        fi
        cd "$old_pwd"
    fi
else
    log "skip-docker-build set — skipping Docker build"
fi

# -------------------------------------------------------------------
# Step 3: Syft SBOM
# -------------------------------------------------------------------
printf '\n'
log "--- Step 3: Syft SBOM generation ---"

SBOM_SPDX="${OUTPUT_DIR}/sbom_laptop.spdx.json"
SBOM_CYCLONE="${OUTPUT_DIR}/sbom_laptop.cyclonedx.json"
SBOM_TABLE="${OUTPUT_DIR}/sbom_laptop.table.txt"
PACKAGE_COUNT=0

if [[ $SKIP_SYFT -eq 0 ]]; then
    SYFT_INSTALLED=0
    test_cmd syft && SYFT_INSTALLED=1

    if [[ $SYFT_INSTALLED -eq 0 ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            dry "syft not installed — would prompt install from: https://github.com/anchore/syft/releases"
        else
            warn "syft not found on PATH. Install via:"
            warn "  curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin"
            warn "  Or download: https://github.com/anchore/syft/releases"
        fi
    fi

    SYFT_VER_CMD="syft version"
    SYFT_SPDX_CMD="syft ${IMAGE_TAG} -o spdx-json='${SBOM_SPDX}'"
    SYFT_CDX_CMD="syft ${IMAGE_TAG} -o cyclonedx-json='${SBOM_CYCLONE}'"
    SYFT_TABLE_CMD="syft ${IMAGE_TAG} -o table='${SBOM_TABLE}'"

    if [[ $DRY_RUN -eq 1 ]]; then
        add_dry_run "Verify syft installed" "$SYFT_VER_CMD" ""
        add_dry_run "Generate SPDX JSON SBOM" "$SYFT_SPDX_CMD" "$SBOM_SPDX"
        add_dry_run "Generate CycloneDX JSON SBOM" "$SYFT_CDX_CMD" "$SBOM_CYCLONE"
        add_dry_run "Generate table SBOM + count packages" "$SYFT_TABLE_CMD" "$SBOM_TABLE"
        dry "Would run: ${SYFT_VER_CMD}"
        dry "Would run: ${SYFT_SPDX_CMD}"
        dry "Would run: ${SYFT_CDX_CMD}"
        dry "Would run: ${SYFT_TABLE_CMD}"
    else
        if [[ $SYFT_INSTALLED -eq 0 ]]; then
            err "syft not installed — cannot generate SBOM"
        else
            syft_ver_line=$(syft version 2>&1 | head -n1)
            ok "syft found: ${syft_ver_line}"

            log "Generating SPDX SBOM -> ${SBOM_SPDX}"
            syft "$IMAGE_TAG" -o "spdx-json=${SBOM_SPDX}" --quiet || warn "syft SPDX generation failed"

            log "Generating CycloneDX SBOM -> ${SBOM_CYCLONE}"
            syft "$IMAGE_TAG" -o "cyclonedx-json=${SBOM_CYCLONE}" --quiet || warn "syft CycloneDX generation failed"

            log "Generating table SBOM -> ${SBOM_TABLE}"
            syft "$IMAGE_TAG" -o "table=${SBOM_TABLE}" --quiet || warn "syft table generation failed"

            if [[ -s "$SBOM_TABLE" ]]; then
                lines=$(wc -l < "$SBOM_TABLE" | tr -d ' ')
                if [[ $lines -gt 2 ]]; then
                    PACKAGE_COUNT=$((lines - 3))
                    [[ $PACKAGE_COUNT -lt 0 ]] && PACKAGE_COUNT=0
                fi
                ok "Syft SBOMs generated — ${PACKAGE_COUNT} packages detected"
            fi
        fi
    fi
else
    log "skip-syft set — skipping SBOM generation"
fi

# -------------------------------------------------------------------
# Step 4: Trivy CVE scan
# -------------------------------------------------------------------
printf '\n'
log "--- Step 4: Trivy CVE scan ---"

TRIVY_SARIF="${OUTPUT_DIR}/trivy_laptop_image.sarif.json"
TRIVY_FULL="${OUTPUT_DIR}/trivy_laptop_image.full.txt"
CVE_SUMMARY="${OUTPUT_DIR}/cve_summary.json"
CVE_CRITICAL=0
CVE_HIGH=0
CVE_MEDIUM=0
CVE_LOW=0
CVE_UNKNOWN=0

if [[ $SKIP_TRIVY -eq 0 ]]; then
    TRIVY_INSTALLED=0
    test_cmd trivy && TRIVY_INSTALLED=1

    if [[ $TRIVY_INSTALLED -eq 0 ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            dry "trivy not installed — would prompt install from: https://github.com/aquasecurity/trivy/releases"
        else
            warn "trivy not found on PATH. Install via:"
            warn "  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"
            warn "  Or download: https://github.com/aquasecurity/trivy/releases"
        fi
    fi

    TRIVY_VER_CMD="trivy --version"
    TRIVY_SARIF_CMD="trivy image --format sarif --output '${TRIVY_SARIF}' ${IMAGE_TAG}"
    TRIVY_FULL_CMD="trivy image --format table --output '${TRIVY_FULL}' ${IMAGE_TAG}"

    if [[ $DRY_RUN -eq 1 ]]; then
        add_dry_run "Verify trivy installed" "$TRIVY_VER_CMD" ""
        add_dry_run "Trivy SARIF CVE report" "$TRIVY_SARIF_CMD" "$TRIVY_SARIF"
        add_dry_run "Trivy table full report" "$TRIVY_FULL_CMD" "$TRIVY_FULL"
        add_dry_run "Parse CVE counts -> cve_summary.json" "parse ${TRIVY_FULL} + write ${CVE_SUMMARY}" "$CVE_SUMMARY"
        dry "Would run: ${TRIVY_VER_CMD}"
        dry "Would run: ${TRIVY_SARIF_CMD}"
        dry "Would run: ${TRIVY_FULL_CMD}"
    else
        if [[ $TRIVY_INSTALLED -eq 0 ]]; then
            err "trivy not installed — cannot run CVE scan"
        else
            trivy_ver_line=$(trivy --version 2>&1 | head -n1)
            ok "trivy found: ${trivy_ver_line}"

            log "Running Trivy SARIF scan -> ${TRIVY_SARIF}"
            trivy image --format sarif --output "$TRIVY_SARIF" "$IMAGE_TAG" >/dev/null 2>&1 || true

            log "Running Trivy full table scan -> ${TRIVY_FULL}"
            trivy image --format table --output "$TRIVY_FULL" "$IMAGE_TAG" >/dev/null 2>&1 || true

            if [[ -s "$TRIVY_FULL" ]]; then
                raw=$(cat "$TRIVY_FULL")
                CVE_CRITICAL=$(printf '%s\n' "$raw" | grep -iE '^\s*CRITICAL\s*\|\s*[0-9]+\s*$' | awk -F'|' '{gsub(/ /,"",$2); print $2}' | paste -sd+ | bc 2>/dev/null || echo 0)
                [[ -z "$CVE_CRITICAL" ]] && CVE_CRITICAL=0
                CVE_HIGH=$(printf '%s\n' "$raw" | grep -iE '^\s*HIGH\s*\|\s*[0-9]+\s*$' | awk -F'|' '{gsub(/ /,"",$2); print $2}' | paste -sd+ | bc 2>/dev/null || echo 0)
                [[ -z "$CVE_HIGH" ]] && CVE_HIGH=0
                CVE_MEDIUM=$(printf '%s\n' "$raw" | grep -iE '^\s*MEDIUM\s*\|\s*[0-9]+\s*$' | awk -F'|' '{gsub(/ /,"",$2); print $2}' | paste -sd+ | bc 2>/dev/null || echo 0)
                [[ -z "$CVE_MEDIUM" ]] && CVE_MEDIUM=0
                CVE_LOW=$(printf '%s\n' "$raw" | grep -iE '^\s*LOW\s*\|\s*[0-9]+\s*$' | awk -F'|' '{gsub(/ /,"",$2); print $2}' | paste -sd+ | bc 2>/dev/null || echo 0)
                [[ -z "$CVE_LOW" ]] && CVE_LOW=0
                CVE_UNKNOWN=$(printf '%s\n' "$raw" | grep -iE '^\s*UNKNOWN\s*\|\s*[0-9]+\s*$' | awk -F'|' '{gsub(/ /,"",$2); print $2}' | paste -sd+ | bc 2>/dev/null || echo 0)
                [[ -z "$CVE_UNKNOWN" ]] && CVE_UNKNOWN=0

                cat > "$CVE_SUMMARY" <<JSON
{
  "critical": ${CVE_CRITICAL},
  "high": ${CVE_HIGH},
  "medium": ${CVE_MEDIUM},
  "low": ${CVE_LOW},
  "unknown": ${CVE_UNKNOWN}
}
JSON
                ok "CVE summary written: CRITICAL=${CVE_CRITICAL}, HIGH=${CVE_HIGH}, MEDIUM=${CVE_MEDIUM}, LOW=${CVE_LOW}, UNKNOWN=${CVE_UNKNOWN}"
            fi
        fi
    fi
else
    log "skip-trivy set — skipping CVE scan"
fi

# -------------------------------------------------------------------
# Step 5: Changelog scan
# -------------------------------------------------------------------
printf '\n'
log "--- Step 5: Changelog + release checklist scan ---"

CHANGELOG_PATH="$(pwd)/CHANGELOG.md"
CHECKLIST_PATH="$(pwd)/RELEASE_CHECKLIST_v0.2.0_rc2.md"
CHANGELOG_OK=0
CHK_SCAN_CMD="Check CHANGELOG.md for v0.2.0-rc2 section + match RELEASE_CHECKLIST items"

if [[ $DRY_RUN -eq 1 ]]; then
    add_dry_run "Changelog verification" "$CHK_SCAN_CMD" ""
    dry "Would read ${CHANGELOG_PATH} and ${CHECKLIST_PATH}"
else
    if [[ -f "$CHANGELOG_PATH" ]]; then
        cl=$(cat "$CHANGELOG_PATH")
        has_rc2=$(printf '%s' "$cl" | grep -cE '0\.2\.0.*rc2|v0\.2\.0-rc2|Unreleased' || true)
        if [[ $has_rc2 -gt 0 ]]; then
            ok "CHANGELOG.md contains release markers (Unreleased/v0.2.0-rc2 patterns)"
            CHANGELOG_OK=1
        else
            warn "CHANGELOG.md found but no v0.2.0-rc2 section marker"
        fi
    else
        warn "CHANGELOG.md not found in project root"
    fi

    if [[ -f "$CHECKLIST_PATH" ]]; then
        rc=$(cat "$CHECKLIST_PATH")
        step10=$(printf '%s' "$rc" | grep -ciE 'step 10|Trivy.*HIGH.*CRITICAL|SBOM.*syft' || true)
        if [[ $step10 -gt 0 ]]; then
            ok "RELEASE_CHECKLIST step 10 items (SBOM+CVE) referenced"
        else
            warn "RELEASE_CHECKLIST found but step 10 markers missing"
        fi
    else
        warn "RELEASE_CHECKLIST_v0.2.0_rc2.md not found in project root"
    fi
fi

# -------------------------------------------------------------------
# Step 6: SBOM output verification + summary table
# -------------------------------------------------------------------
printf '\n'
log "--- Step 6: Output verification + summary ---"

VERIFY_OK=1

printf '\e[36m%-25s %-8s %-12s %s\e[0m\n' "FILE" "EXISTS" "SIZE_BYTES" "PATH"

verify_file() {
    local name="$1" path="$2" skip="$3"
    local exists=0 size=0 status color
    if [[ $skip -eq 1 ]]; then
        status="SKIP"; color="\e[90m"
    else
        if [[ $DRY_RUN -eq 1 ]]; then
            dry "Would check existence/size of: ${path}"
            exists=1; size=0
        else
            if [[ -s "$path" ]]; then
                exists=1
                size=$(wc -c < "$path" | tr -d ' ')
            else
                warn "Missing or empty: ${name}"
                VERIFY_OK=0
            fi
        fi
        if [[ $exists -eq 1 ]]; then
            status="OK"; color="\e[32m"
        else
            status="MISS"; color="\e[31m"
        fi
    fi
    printf "${color}%-25s %-8s %-12s %s\e[0m\n" "$name" "$status" "$size" "$path"
}

verify_file "SBOM SPDX JSON"      "$SBOM_SPDX"    $SKIP_SYFT
verify_file "SBOM CycloneDX JSON" "$SBOM_CYCLONE" $SKIP_SYFT
verify_file "SBOM table text"     "$SBOM_TABLE"   $SKIP_SYFT
verify_file "Trivy SARIF report"  "$TRIVY_SARIF"  $SKIP_TRIVY
verify_file "Trivy full report"   "$TRIVY_FULL"   $SKIP_TRIVY
verify_file "CVE summary JSON"    "$CVE_SUMMARY"  $SKIP_TRIVY

# -------------------------------------------------------------------
# DryRun: write dryrun_plan.json and exit
# -------------------------------------------------------------------
if [[ $DRY_RUN -eq 1 ]]; then
    mkdir -p "$OUTPUT_DIR"
    DRY_PLAN_PATH="${OUTPUT_DIR}/dryrun_plan.json"
    GEN_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    {
        printf '{\n'
        printf '  "generated_at": "%s",\n' "$GEN_AT"
        printf '  "params": {\n'
        printf '    "DryRun": %s,\n'           "$DRY_RUN"
        printf '    "SkipDockerBuild": %s,\n'  "$SKIP_DOCKER_BUILD"
        printf '    "SkipSyft": %s,\n'         "$SKIP_SYFT"
        printf '    "SkipTrivy": %s,\n'        "$SKIP_TRIVY"
        printf '    "Dockerfile": "%s",\n'     "$DOCKERFILE"
        printf '    "ImageTag": "%s",\n'       "$IMAGE_TAG"
        printf '    "OutputDir": "%s"\n'       "$OUTPUT_DIR"
        printf '  },\n'
        printf '  "steps": [\n'
        n=${#DRY_STEP_DESC[@]}
        for ((i=0; i<n; i++)); do
            desc="${DRY_STEP_DESC[$i]}"
            cmd="${DRY_STEP_CMD[$i]}"
            expected="${DRY_STEP_EXPECTED[$i]}"
            expected_json="[]"
            if [[ -n "$expected" ]]; then
                expected_json="[\"${expected}\"]"
            fi
            comma=","
            [[ $i -eq $((n-1)) ]] && comma=""
            printf '    {\n'
            printf '      "step": "%s",\n'      "$desc"
            printf '      "command": "%s",\n'   "$cmd"
            printf '      "expected_outputs": %s\n' "$expected_json"
            printf '    }%s\n' "$comma"
        done
        printf '  ]\n'
        printf '}\n'
    } > "$DRY_PLAN_PATH"

    printf '\n'
    ok "DryRun plan written: ${DRY_PLAN_PATH}"
    ok "DryRun commands count: ${n}"
    exit 0
fi

# -------------------------------------------------------------------
# Step 7: Exit code determination
# -------------------------------------------------------------------
printf '\n'
log "--- Step 7: Exit code determination ---"

if [[ $CVE_CRITICAL -ge 1 ]]; then
    err "CVE CRITICAL count = ${CVE_CRITICAL} -> exit 4"
    exit 4
fi

if [[ $VERIFY_OK -eq 0 ]]; then
    err "SBOM/CVE outputs missing or empty -> exit 3"
    exit 3
fi

if [[ $WARNINGS -gt 0 ]]; then
    warn "${WARNINGS} warning(s) encountered -> exit 1"
    exit 1
fi

ok "All checks passed cleanly -> exit 0"
exit 0
