# ── Stage 1: build Angular ──────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# ── Stage 2: Caddy sirve el dist ────────────────────────────────────────────
FROM caddy:2-alpine AS runner

COPY --from=builder /app/dist/kpi-dashboard/browser /usr/share/caddy
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80
