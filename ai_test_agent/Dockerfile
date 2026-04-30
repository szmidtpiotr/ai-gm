# Node + Playwright (Chromium) for admin Test Runner — HTTP: POST /agent/run
# Obraz MUSI odpowiadać wersji "playwright" w package-lock.json (npm ci instaluje te same binaria).
FROM mcr.microsoft.com/playwright:v1.59.1-jammy
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY agent ./agent
COPY playwright ./playwright
ENV AGENT_PORT=4000
EXPOSE 4000
CMD ["node", "agent/server.js"]
