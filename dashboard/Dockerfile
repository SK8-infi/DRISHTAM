# ── Stage 1: Install dependencies ────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline --no-audit

# ── Stage 2: Build ───────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time env: API URL is baked into the Next.js bundle
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Next.js standalone output for smaller image
RUN npm run build

# ── Stage 3: Production ─────────────────────────────────────
FROM node:20-alpine AS production

# Security: Don't run as root
RUN addgroup -g 1001 -S drishtam && \
    adduser -S drishtam -u 1001 -G drishtam
WORKDIR /app

# Next.js standalone output
COPY --from=builder --chown=drishtam:drishtam /app/.next/standalone ./
COPY --from=builder --chown=drishtam:drishtam /app/.next/static ./.next/static
COPY --from=builder --chown=drishtam:drishtam /app/public ./public

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

USER drishtam
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
