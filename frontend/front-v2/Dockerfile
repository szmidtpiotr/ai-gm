# Multi-stage: Node buduje bundle → Nginx serwuje dist/ (deployment opcja B, sekcja 2).
# Serwowane pod /v2/ (base w vite.config.ts + router basename).

# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

# ── Stage 2: serve ──────────────────────────────────────────────────────────
FROM nginx:alpine AS serve
COPY nginx.front-v2.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html/v2
EXPOSE 80
