FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci --no-audit --no-fund
COPY apps/web apps/web
COPY packages/contracts packages/contracts
ENV NEXT_TELEMETRY_DISABLED=1 PAO_BUILD_CHECK=1 PAO_API_URL=http://api:8000
RUN node node_modules/next/dist/bin/next build apps/web
FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PAO_BUILD_CHECK=1 PAO_API_URL=http://api:8000
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci --omit=dev --no-audit --no-fund
COPY --from=build /app/apps/web/.pao-build-check apps/web/.pao-build-check
COPY apps/web/next.config.mjs apps/web/next.config.mjs
USER node
CMD ["node", "node_modules/next/dist/bin/next", "start", "apps/web", "--hostname", "0.0.0.0", "--port", "3000"]
