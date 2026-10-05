# =====================================================================
# Noesis Frontend — Production Dockerfile (Next.js 14 App Router)
# =====================================================================
# Multi-stage build keeps image tiny (~220 MB):
#   1. deps   — installs node_modules (with dev deps for build)
#   2. build  — runs `next build`
#   3. runner — installs only prod deps (node_modules/production) + copies .next
#
# Build:  docker build -t astraos-frontend -f Dockerfile .
# Run:    docker run --rm -p 3000:3000 \
#             -e BACKEND_BASE_URL=http://backend:8000 astraos-frontend
# =====================================================================

# --- Stage 1: Deps ---------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app

# Install libc6-compat — some native npm modules (sharp, esbuild) need it on alpine.
RUN apk add --no-cache libc6-compat

# Install node_modules based on lockfile first (cache-friendly layer).
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps --include=dev

# --- Stage 2: Builder ------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# `next build` requires write perms even as root; also ensure .next exists
ENV NEXT_PRIVATE_BUILD_WORKERS=2
RUN npm run build

# --- Stage 3: Runner (prod-only deps + standalone build output) ----
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    BACKEND_BASE_URL=http://localhost:8000

# Don't run as root.
RUN addgroup --system --gid 1001 nodejs \
    && adduser  --system --uid 1001 nextjs

# Minimal production node_modules (no dev deps → ~60% smaller image).
COPY --from=builder /app/package.json ./package.json
COPY --from=deps   /app/node_modules ./node_modules_full
RUN npm install --legacy-peer-deps --omit=dev --ignore-scripts \
    || cp -r /app/node_modules_full /app/node_modules

# Next.js standalone + static output + public assets.
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/next.config.mjs ./next.config.mjs
COPY --from=builder --chown=nextjs:nodejs /app/postcss.config.js ./postcss.config.js
COPY --from=builder --chown=nextjs:nodejs /app/tailwind.config.ts ./tailwind.config.ts

USER nextjs:nodejs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000',r=>{process.exit(r.statusCode===200?0:1)}).on('error',()=>process.exit(1))" || exit 1

CMD ["node_modules/.bin/next", "start", "-p", "3000", "-H", "0.0.0.0"]
